"""
Settings Tab - Application configuration and preferences
Isolated module for settings-related functionality
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import tkinter.messagebox as messagebox
import json
import threading
from pathlib import Path
import os
import sys
import glob
import shutil
import subprocess
from typing import Any, Dict, Optional, List
import logger_util
from logger_util import log_message
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import ui_thread - graceful fallback if not available
try:
    from ui_thread import showinfo as ui_showinfo
except (ImportError, ModuleNotFoundError):
    ui_showinfo = messagebox.showinfo

# Phase Sub-Zero-D: Import debug UI event tracking
try:
    from debug_logger import get_logger, debug_ui_event as _debug_ui_event
    _settings_debug_logger = get_logger("SettingsTab")
    debug_ui_event = _debug_ui_event  # Use actual decorator
except ImportError:
    _settings_debug_logger = None
    # Fallback: no-op decorator if import fails
    def debug_ui_event(logger):
        def decorator(func):
            return func
        return decorator

PROJECT_ROOT = Path(__file__).resolve().parents[4]

# AI Assistant Dialog import
try:
    from .ai_assistant_dialog import show_ai_assistant
    AI_ASSISTANT_AVAILABLE = True
except ImportError:
    AI_ASSISTANT_AVAILABLE = False
    log_message("SETTINGS: AI assistant dialog not available")

try:
    from dialogs.ask_ai_dialog import show_ask_ai_dialog
    ASK_AI_DIALOG_AVAILABLE = True
except ImportError as exc:
    ASK_AI_DIALOG_AVAILABLE = False
    log_message(f"SETTINGS: Ask AI dialog not available ({exc})")

# Version manager import for blueprint snapshots
try:
    from launcher.version_manager import VersionManager
    VERSION_MANAGER_AVAILABLE = True
except Exception as exc:
    VERSION_MANAGER_AVAILABLE = False
    log_message(f"SETTINGS: Version manager unavailable ({exc})")

# Enhanced debug viewer imports
# Debug wiring quick reference:
#   - Summary aggregation: Data/enhanced_debug_viewer.py:1150 (_render bug summary)
#   - Tracker consolidation: Data/bug_tracker.py:2056 (consolidate_registry/_fold_bug_entries)
#   - Change watcher diffs: Data/code_change_watcher/api.py:90 (_record_change/_notify_bug_tracker)
# Use these anchors when adjusting SettingsTab debug sections to keep behaviour consistent.
DEFAULT_TRUSTED_PATTERNS = [
    "data/user_prefs/",
    "data/debug/",
    "data/history-nest/",
    "data/logs/",
    "data/training_runs/",
    "data/training_data-sets/",
]

try:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from enhanced_debug_viewer import EnhancedDebugViewer, BugSummaryPanel
    ENHANCED_DEBUG_AVAILABLE = True
except ImportError:
    ENHANCED_DEBUG_AVAILABLE = False
    log_message("Enhanced debug viewer not available")

try:
    from bug_tracker import get_bug_tracker
except Exception as exc:
    get_bug_tracker = None  # type: ignore
    log_message(f"SETTINGS: Bug tracker unavailable ({exc})")

from tabs.base_tab import BaseTab
from logger_util import set_tab_enabled, get_tab_state
from config import (TRAINER_ROOT, DATA_DIR, MODELS_DIR, TODOS_DIR, TRAINING_DATA_DIR,
                    create_todo_file, list_todo_files, read_todo_file,
                    update_todo_file, delete_todo_file, move_todo_to_completed,
                    get_project_todos_dir, create_project_todo_file, list_project_todo_files,
                    list_all_projects_with_todos, move_project_todo_to_completed,
                    add_plan_link_to_todo, remove_plan_link_from_todo, set_plan_links,
                    get_bug_details_for_agent)

VECTOR_MCP_SCRIPT = PROJECT_ROOT / "scripts" / "run_vector_mcp.py"
VECTOR_MCP_LOG_DIR = DATA_DIR / "DeBug"
try:
    from living_projects.living_project_manager import get_manager as get_living_project_manager
    from living_projects.living_project_manager import LivingProjectManager
except Exception:
    get_living_project_manager = None

WATCHER_AVAILABLE = False
try:
    from code_change_watcher import (
        configure_watcher,
        start_watcher,
        stop_watcher,
        scan_now as watcher_scan_now,
        rebuild_baseline as watcher_rebuild_baseline,
        get_last_scan_info,
        set_gatekeeper_enabled,
        set_gate_callback,
        set_trusted_patterns as watcher_set_trusted_patterns,
        add_trusted_patterns as watcher_add_trusted_patterns,
        pause_gatekeeper as watcher_pause_gatekeeper,
        resume_gatekeeper as watcher_resume_gatekeeper,
        duplicate_version as watcher_duplicate_version,
    )
    WATCHER_AVAILABLE = True
except Exception as exc:  # pragma: no cover
    log_message(f"SETTINGS: Change watcher not available: {exc}")

if not WATCHER_AVAILABLE:
    def configure_watcher(**_kwargs):
        return None
    def start_watcher():
        return None
    def stop_watcher():
        return None
    def watcher_scan_now():
        return None
    def watcher_rebuild_baseline():
        return None
    def get_last_scan_info():
        return None
    def set_gatekeeper_enabled(*_args, **_kwargs):
        return None
    def set_gate_callback(*_args, **_kwargs):
        return None
    def watcher_set_trusted_patterns(*_args, **_kwargs):
        return None
    def watcher_add_trusted_patterns(*_args, **_kwargs):
        return None
    def watcher_pause_gatekeeper(*_args, **_kwargs):
        return None
    def watcher_resume_gatekeeper(*_args, **_kwargs):
        return None
    def watcher_duplicate_version(*_args, **_kwargs):
        return {"files": 0, "total": 0}


class SettingsTab(BaseTab):
    """Application settings and configuration tab"""

    def __init__(self, parent, root, style, main_gui=None, tab_instances=None):
        super().__init__(parent, root, style)

        # Reference to main GUI (for accessing other tabs)
        self.main_gui = main_gui
        self.tab_instances = tab_instances

        # Debug tab variables
        self.log_poll_job = None
        self.current_log_file = None
        self.last_read_position = 0
        self.log_file_paths = {} # Corrected indentation
        self.tab_enabled_vars = {} # For managing tab visibility
        self.reorder_mode = tk.StringVar(value='static') # New setting for tab reordering
        # Settings file
        self.settings_file = DATA_DIR / "settings.json"
        self.settings = self.load_settings()
        # Lazy terminal init flag
        self.terminal_initialized = False
        # Internal flag to suppress reorder mode popups during programmatic changes
        self._suppress_reorder_popup = False
        # Internal mapping from (tab_name, panel_header_text) -> file path (if resolvable)
        self.panel_file_map = {}
        # Current project context for unified ToDo manager (set by Projects panel)
        self.current_project_context = None
        self.change_watcher_settings = self._load_change_watcher_settings()
        self._change_watcher_active = False
        # Vector MCP bridge state
        self.vector_mcp_status_var = tk.StringVar(value="Disabled (On Hold)")
        self._suppress_vector_mcp_toggle = False
        self._vector_mcp_initial_pref = bool(self.settings.get('custom_code', {}).get('vector_mcp_enabled', False))

        # Install a global Tk callback exception hook to capture UI errors in logs
        try:
            def _tk_error_hook(exc, value, tb):
                try:
                    logger_util.log_exception("TK CALLBACK ERROR", exc_info=(exc, value, tb), tab='general')
                except Exception:
                    pass
            if hasattr(self.root, 'report_callback_exception'):
                self.root.report_callback_exception = _tk_error_hook
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Plan helpers (shared between TODO dialogs)
    # ------------------------------------------------------------------ #

    def _normalize_plan_key(self, raw_title: str | None) -> str:
        """Strip the 'Plan:' prefix so we can match LINKED_PLAN metadata."""
        if not raw_title:
            return ''
        cleaned = raw_title.strip()
        if cleaned.lower().startswith('plan:'):
            return cleaned.split(':', 1)[1].strip()
        return cleaned

    def _extract_linked_plan_keys(self, todo_data: dict | None) -> list[str]:
        """Return all plan keys associated with a todo record."""
        if not isinstance(todo_data, dict):
            return []
        plans = todo_data.get('linked_plans') or []
        results = [p.strip() for p in plans if isinstance(p, str) and p.strip()]
        if not results:
            legacy = (todo_data.get('linked_plan') or '').strip()
            if legacy:
                results = [legacy]
        # Deduplicate while preserving order
        deduped = []
        seen = set()
        for plan in results:
            if plan in seen:
                continue
            seen.add(plan)
            deduped.append(plan)
        return deduped

    def _format_todo_display_text(self, todo_data: dict | None, category: str) -> str:
        """Return display text including plan + type prefix for tree listings."""
        category = (category or '').strip().lower()
        if category == 'plans':
            return (todo_data or {}).get('title', '') or 'Plan'
        title = (todo_data or {}).get('title', '').strip() or 'Untitled Item'
        type_map = {
            'tasks': 'Task',
            'bugs': 'Bug',
            'work_orders': 'Work-Order',
            'notes': 'Note',
            'tests': 'Test',
        }
        type_label = type_map.get(category, category.title() if category else 'Item')
        plan_keys = self._extract_linked_plan_keys(todo_data)
        if plan_keys and category != 'plans':
            cleaned_title, _ = self._strip_legacy_plan_header(title, type_label)
            title = cleaned_title or title
            primary = plan_keys[0]
            suffix = ', '.join(plan_keys[1:])
            plan_text = f"Plan:{primary}"
            if suffix:
                plan_text = f"{plan_text} (+{len(plan_keys)-1})"
            return f"{plan_text} | {type_label}: {title}"
        return f"{type_label}: {title}"

    def _strip_legacy_plan_header(self, title: str, type_label: str) -> tuple[str, bool]:
        """Remove pre-existing Plan/Type prefixes from legacy titles."""
        if not title:
            return title, False
        text = title.strip()
        lowered = text.lower()
        if not lowered.startswith('plan:'):
            return text, False
        if '|' not in text:
            return text, True
        _, remainder = text.split('|', 1)
        remainder = remainder.strip()
        type_prefix = f"{type_label.lower()}:"
        if remainder.lower().startswith(type_prefix):
            parts = remainder.split(':', 1)
            if len(parts) == 2:
                remainder = parts[1].strip()
        return remainder or text, True

    def _collect_plan_children_records(self, plan_key: str) -> tuple[list[dict], list[dict]]:
        """Return (open_children, completed_children) linked to plan_key."""
        open_children: list[dict] = []
        completed_children: list[dict] = []
        if not plan_key:
            return open_children, completed_children

        def _todo_has_plan(todo: dict) -> bool:
            return plan_key in self._extract_linked_plan_keys(todo)

        def _collect_from_category(category: str, target_list: list[dict], completed: bool = False):
            try:
                files = list_todo_files(category)
            except Exception:
                return
            for path in files:
                try:
                    data = read_todo_file(path)
                except Exception:
                    continue
                if _todo_has_plan(data):
                    target_list.append({
                        'category': category,
                        'title': data.get('title', path.stem),
                        'details': data.get('details', ''),
                        'filepath': data.get('filepath', str(path)),
                        'path': path,
                        'completed': completed,
                        'project': None,
                    })

        for cat in ('tasks', 'bugs', 'work_orders', 'notes', 'tests'):
            _collect_from_category(cat, open_children, completed=False)
        _collect_from_category('completed', completed_children, completed=True)

        # Include project-scoped todos
        try:
            project_names = list_all_projects_with_todos()
        except Exception:
            project_names = []
        for project_name in project_names:
            for category in ('tasks', 'bugs', 'work_orders', 'notes', 'tests'):
                try:
                    files = list_project_todo_files(project_name, category)
                except Exception:
                    continue
                for path in files:
                    try:
                        data = read_todo_file(path)
                    except Exception:
                        continue
                    if _todo_has_plan(data):
                        open_children.append({
                            'category': category,
                            'title': data.get('title', path.stem),
                            'details': data.get('details', ''),
                            'filepath': data.get('filepath', str(path)),
                            'path': path,
                            'completed': False,
                            'project': project_name,
                        })
            try:
                completed_files = list_project_todo_files(project_name, 'completed')
            except Exception:
                completed_files = []
            for path in completed_files:
                try:
                    data = read_todo_file(path)
                except Exception:
                    continue
                if _todo_has_plan(data):
                    completed_children.append({
                        'category': 'completed',
                        'title': data.get('title', path.stem),
                        'details': data.get('details', ''),
                        'filepath': data.get('filepath', str(path)),
                        'path': path,
                        'completed': True,
                        'project': project_name,
                    })

        return open_children, completed_children

    def _collect_available_plans(self) -> List[Dict[str, Any]]:
        """Return list of plan records across system and projects."""
        records: List[Dict[str, Any]] = []

        def _append_record(path: Path, scope: str, project: Optional[str]):
            try:
                data = read_todo_file(path)
            except Exception:
                return
            plan_title = data.get('title', path.stem)
            linked = data.get('linked_plans') or []
            plan_key = linked[0] if linked else self._normalize_plan_key(plan_title)
            if not plan_key:
                plan_key = path.stem
            scope_label = "System" if scope == 'system' else f"Project • {project}"
            label = f"{scope_label} | {plan_title}"
            records.append({
                'label': label,
                'plan_key': plan_key,
                'title': plan_title,
                'path': path,
                'scope': scope,
                'project': project,
            })

        try:
            for path in list_todo_files('plans'):
                _append_record(path, 'system', None)
        except Exception:
            pass

        try:
            for project_name in list_all_projects_with_todos():
                try:
                    plan_files = list_project_todo_files(project_name, 'plans')
                except Exception:
                    continue
                for path in plan_files:
                    _append_record(path, 'project', project_name)
        except Exception:
            pass

        records.sort(key=lambda rec: rec['label'].lower())
        return records

    def _build_plan_preview_text(self, plan_key: str) -> str:
        """Render plan child todos for preview dialogs."""
        open_children, completed_children = self._collect_plan_children_records(plan_key)
        lines = [f"Open ({len(open_children)}):"]
        if open_children:
            for child in open_children[:20]:
                proj = child.get('project')
                scope = f"{child['category']}" + (f" @ {proj}" if proj else "")
                lines.append(f"  • [{scope}] {child.get('title') or '(Untitled)'}")
        else:
            lines.append("  • None")
        lines.append("")
        lines.append(f"Completed ({len(completed_children)}):")
        if completed_children:
            for child in completed_children[:20]:
                proj = child.get('project')
                scope = f"{child['category']}" + (f" @ {proj}" if proj else "")
                lines.append(f"  • [{scope}] {child.get('title') or '(Untitled)'}")
        else:
            lines.append("  • None")
        if len(open_children) > 20 or len(completed_children) > 20:
            lines.append("")
            lines.append("… additional items omitted")
        return "\n".join(lines)

    def _resolve_todo_path(self, category: str, filename: str, project_name: Optional[str] = None) -> Optional[Path]:
        """Get absolute path for a todo file."""
        if not filename or not category:
            return None
        try:
            if project_name:
                base = get_project_todos_dir(project_name)
            else:
                base = TODOS_DIR
            path = base / category / filename
            return path if path.exists() else None
        except Exception:
            return None

    def _resolve_todo_info(self, category: str, filename: str, project_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Return todo metadata for the specified selection."""
        path = self._resolve_todo_path(category, filename, project_name)
        if not path:
            return None
        try:
            data = read_todo_file(path)
        except Exception:
            data = {}
        return {
            'category': category,
            'filename': filename,
            'project': project_name,
            'path': path,
            'data': data,
        }

    def _iterate_all_todo_records(self):
        """Yield all todo file paths across system and project scopes."""
        categories = ('tasks', 'bugs', 'work_orders', 'notes', 'tests', 'plans', 'completed')
        for category in categories:
            try:
                for path in list_todo_files(category):
                    yield {'path': path, 'category': category, 'project': None}
            except Exception:
                continue
        try:
            for project_name in list_all_projects_with_todos():
                for category in categories:
                    try:
                        for path in list_project_todo_files(project_name, category):
                            yield {'path': path, 'category': category, 'project': project_name}
                    except Exception:
                        continue
        except Exception:
            pass

    def _replace_plan_key_in_all_todos(self, old_key: str, new_key: Optional[str]) -> None:
        """Replace occurrences of old plan key with new key across all todos."""
        normalized_old = self._normalize_plan_key(old_key)
        normalized_new = self._normalize_plan_key(new_key) if new_key else None
        if not normalized_old:
            return
        for record in self._iterate_all_todo_records():
            path = record['path']
            try:
                data = read_todo_file(path)
            except Exception:
                continue
            plans = self._extract_linked_plan_keys(data)
            if normalized_old not in plans:
                continue
            remove_plan_link_from_todo(path, normalized_old)
            if normalized_new:
                add_plan_link_to_todo(path, normalized_new)

    def _archive_plan_file(self, plan_record: Dict[str, Any]) -> None:
        """Move a plan file into an archived subdirectory."""
        path = plan_record.get('path')
        if not isinstance(path, Path) or not path.exists():
            return
        archive_dir = path.parent / "archived"
        try:
            archive_dir.mkdir(parents=True, exist_ok=True)
            target = archive_dir / path.name
            counter = 1
            while target.exists():
                target = archive_dir / f"{path.stem}_archived{counter}{path.suffix}"
                counter += 1
            path.rename(target)
        except Exception as exc:
            log_message(f"SETTINGS: Failed to archive plan file {path}: {exc}")

    def _require_conformer_for_plan_action(
        self,
        parent_window,
        operation_type: str,
        operation_details: Dict[str, Any]
    ) -> bool:
        """Gate plan operations through the conformer queue when available."""
        try:
            from conformer_ui_integration import check_operation_with_ui
        except ImportError:
            log_message(f"SETTINGS: Conformer UI integration unavailable; allowing {operation_type}")
            return True
        try:
            allowed = check_operation_with_ui(
                parent_window=parent_window or self.root,
                variant_id="todo_manager",
                operation_type=operation_type,
                operation_details=operation_details,
                model_class="Skilled",
                on_approved=None
            )
            return bool(allowed)
        except Exception as exc:
            log_message(f"SETTINGS: Conformer approval failed for {operation_type}: {exc}")
            messagebox.showerror(
                "Conformer Error",
                f"Unable to finish '{operation_type}'. Check conformer logs and try again.",
                parent=parent_window or self.root
            )
            return False

    def _open_link_todo_to_plan_dialog(
        self,
        parent: tk.Toplevel,
        todo_info: Optional[Dict[str, Any]],
        refresh_cb,
        preferred_project: Optional[str] = None
    ) -> None:
        """Display dialog for linking the selected todo to a plan."""
        if not todo_info:
            messagebox.showinfo("Select Todo", "Select a todo before linking to a plan.", parent=parent)
            return
        category = todo_info.get('category')
        if category in ('plans', None):
            messagebox.showinfo("Unsupported", "Plans cannot be linked to another plan.", parent=parent)
            return
        plan_records = self._collect_available_plans()
        if not plan_records:
            messagebox.showinfo("No Plans", "No plans exist yet. Create a plan first.", parent=parent)
            return
        if preferred_project:
            def _plan_weight(rec: Dict[str, Any]):
                if rec.get('scope') == 'project' and rec.get('project') == preferred_project:
                    return (0, rec['label'].lower())
                if rec.get('scope') == 'project':
                    return (1, rec['label'].lower())
                return (2, rec['label'].lower())
            plan_records = sorted(plan_records, key=_plan_weight)

        existing_plans = self._extract_linked_plan_keys(todo_info.get('data'))
        dialog = tk.Toplevel(parent)
        dialog.title("Link Todo to Plan")
        dialog.transient(parent)
        dialog.grab_set()

        ttk.Label(dialog, text=f"Todo: {todo_info.get('data', {}).get('title') or todo_info.get('filename', '')}", font=("Arial", 11, "bold")).pack(padx=8, pady=(8,4))
        ttk.Label(dialog, text=f"Current Plans: {', '.join(existing_plans) if existing_plans else 'None'}").pack(padx=8, pady=(0,8))

        plan_var = tk.StringVar(value=plan_records[0]['label'])
        ttk.Label(dialog, text="Select Plan:").pack(padx=8, anchor=tk.W)
        plan_combo = ttk.Combobox(dialog, textvariable=plan_var, values=[rec['label'] for rec in plan_records], state='readonly', width=60)
        plan_combo.current(0)
        plan_combo.pack(padx=8, fill=tk.X)

        preview = scrolledtext.ScrolledText(dialog, height=12, width=70)
        preview.pack(padx=8, pady=8, fill=tk.BOTH, expand=True)

        def _refresh_preview(_evt=None):
            idx = plan_combo.current()
            preview.delete('1.0', tk.END)
            if idx < 0 or idx >= len(plan_records):
                preview.insert(tk.END, "Select a plan to view linked todos.")
                return
            plan_key = plan_records[idx].get('plan_key') or ''
            if not plan_key:
                preview.insert(tk.END, "Plan key missing. Cannot display preview.")
                return
            preview.insert(tk.END, self._build_plan_preview_text(plan_key))

        plan_combo.bind("<<ComboboxSelected>>", _refresh_preview)
        _refresh_preview()

        btn_row = ttk.Frame(dialog)
        btn_row.pack(fill=tk.X, padx=8, pady=(0,8))
        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=1)

        def _confirm_link():
            idx = plan_combo.current()
            if idx < 0 or idx >= len(plan_records):
                messagebox.showinfo("Select Plan", "Choose a plan before linking.", parent=dialog)
                return
            plan_record = plan_records[idx]
            plan_key = plan_record.get('plan_key') or self._normalize_plan_key(plan_record.get('title'))
            if not plan_key:
                messagebox.showerror("Plan Error", "Unable to determine plan identifier.", parent=dialog)
                return
            todo_path = todo_info.get('path')
            operation_allowed = self._require_conformer_for_plan_action(
                dialog,
                "link_todo_plan",
                {
                    "todo_title": todo_info.get('data', {}).get('title') or todo_info.get('filename'),
                    "todo_file": str(todo_path) if isinstance(todo_path, Path) else "",
                    "todo_category": todo_info.get('category'),
                    "todo_project": todo_info.get('project'),
                    "current_plans": existing_plans,
                    "target_plan": {
                        "key": plan_key,
                        "title": plan_record.get('title'),
                        "scope": plan_record.get('scope'),
                        "project": plan_record.get('project'),
                    },
                    "plan_preview": self._build_plan_preview_text(plan_key),
                }
            )
            if not operation_allowed:
                messagebox.showinfo("Link Cancelled", "Conformer approval is required to link this todo.", parent=dialog)
                return
            if not isinstance(todo_path, Path) or not todo_path.exists():
                messagebox.showerror("Missing File", "Unable to locate todo file on disk.", parent=dialog)
                return
            add_plan_link_to_todo(todo_path, plan_key)
            plan_path = plan_record.get('path')
            if isinstance(plan_path, Path) and plan_path.exists():
                try:
                    set_plan_links(plan_path, [plan_key])
                except Exception as exc:
                    log_message(f"SETTINGS: Failed to normalize plan metadata for '{plan_key}': {exc}")
            try:
                refresh_cb()
            except Exception:
                pass
            dialog.grab_release()
            dialog.destroy()

            if existing_plans and plan_key not in existing_plans:
                other = existing_plans[0]
                if messagebox.askyesno("Merge Plans?", f"This todo is now shared between '{other}' and '{plan_record.get('title')}'. Merge these plans now?", parent=parent):
                    self._open_merge_plans_dialog(parent, refresh_cb, initial_from=other, initial_into=plan_key)
            else:
                messagebox.showinfo("Linked", f"Todo linked to plan '{plan_record.get('title')}'.", parent=parent)

        ttk.Button(btn_row, text="Link Todo", command=_confirm_link, style='Action.TButton').grid(row=0, column=0, sticky=tk.EW, padx=(0,4))
        ttk.Button(btn_row, text="Cancel", command=lambda: (dialog.grab_release(), dialog.destroy()), style='Select.TButton').grid(row=0, column=1, sticky=tk.EW)

    def _open_merge_plans_dialog(self, parent: tk.Toplevel, refresh_cb, initial_from: Optional[str] = None, initial_into: Optional[str] = None) -> None:
        """Show dialog to merge two plans."""
        plan_records = self._collect_available_plans()
        if len(plan_records) < 2:
            messagebox.showinfo("Need Plans", "At least two plans are required to merge.", parent=parent)
            return

        dialog = tk.Toplevel(parent)
        dialog.title("Merge Plans")
        dialog.transient(parent)
        dialog.grab_set()

        labels = [rec['label'] for rec in plan_records]
        from_var = tk.StringVar(value=labels[0])
        into_var = tk.StringVar(value=labels[1])
        new_name_var = tk.StringVar()

        def _set_initial_selection(var, key_hint):
            if not key_hint:
                return
            key_hint_norm = self._normalize_plan_key(key_hint)
            for idx, rec in enumerate(plan_records):
                rec_key = rec.get('plan_key') or self._normalize_plan_key(rec.get('title'))
                if rec_key == key_hint_norm:
                    var.set(rec['label'])
                    break

        _set_initial_selection(from_var, initial_from)
        _set_initial_selection(into_var, initial_into)

        form = ttk.Frame(dialog)
        form.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Merge From:").grid(row=0, column=0, sticky=tk.W, pady=(0,4))
        from_combo = ttk.Combobox(form, textvariable=from_var, values=labels, state='readonly')
        from_combo.grid(row=0, column=1, sticky=tk.EW, pady=(0,4))

        ttk.Label(form, text="Merge Into:").grid(row=1, column=0, sticky=tk.W, pady=(0,4))
        into_combo = ttk.Combobox(form, textvariable=into_var, values=labels, state='readonly')
        into_combo.grid(row=1, column=1, sticky=tk.EW, pady=(0,4))

        ttk.Label(form, text="Resulting Plan Name:").grid(row=2, column=0, sticky=tk.W, pady=(0,4))
        ttk.Entry(form, textvariable=new_name_var).grid(row=2, column=1, sticky=tk.EW, pady=(0,4))

        preview_frame = ttk.Frame(form)
        preview_frame.grid(row=3, column=0, columnspan=2, sticky=tk.NSEW, pady=(8,0))
        form.rowconfigure(3, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.columnconfigure(1, weight=1)

        from_preview = scrolledtext.ScrolledText(preview_frame, height=12)
        into_preview = scrolledtext.ScrolledText(preview_frame, height=12)
        from_preview.grid(row=0, column=0, sticky=tk.NSEW, padx=(0,4))
        into_preview.grid(row=0, column=1, sticky=tk.NSEW, padx=(4,0))

        def _update_previews(_evt=None):
            for combo, preview in ((from_combo, from_preview), (into_combo, into_preview)):
                preview.delete('1.0', tk.END)
                label = combo.get()
                try:
                    idx = labels.index(label)
                except ValueError:
                    preview.insert(tk.END, "Select a plan to preview.")
                    continue
                plan_key = plan_records[idx].get('plan_key') or self._normalize_plan_key(plan_records[idx].get('title'))
                if not plan_key:
                    preview.insert(tk.END, "Plan key missing.")
                    continue
                preview.insert(tk.END, self._build_plan_preview_text(plan_key))
            # Update rename entry default to destination title
            try:
                idx = labels.index(into_combo.get())
                new_name_var.set(plan_records[idx].get('title', ''))
            except ValueError:
                pass

        from_combo.bind("<<ComboboxSelected>>", _update_previews)
        into_combo.bind("<<ComboboxSelected>>", _update_previews)
        _update_previews()

        btn_row = ttk.Frame(dialog)
        btn_row.pack(fill=tk.X, padx=8, pady=8)
        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=1)

        def _confirm_merge():
            try:
                src_idx = labels.index(from_var.get())
                dst_idx = labels.index(into_var.get())
            except ValueError:
                messagebox.showerror("Select Plans", "Select both source and destination plans.", parent=dialog)
                return
            if src_idx == dst_idx:
                messagebox.showerror("Invalid Selection", "Select two different plans to merge.", parent=dialog)
                return
            src_rec = plan_records[src_idx]
            dst_rec = plan_records[dst_idx]
            if src_rec['scope'] != dst_rec['scope'] or src_rec.get('project') != dst_rec.get('project'):
                messagebox.showerror("Scope Mismatch", "Plans must belong to the same scope/project to merge.", parent=dialog)
                return

            new_title = (new_name_var.get() or dst_rec.get('title') or '').strip()
            if not new_title:
                messagebox.showerror("Missing Name", "Provide a name for the merged plan.", parent=dialog)
                return

            src_key = src_rec.get('plan_key') or self._normalize_plan_key(src_rec.get('title'))
            dst_key = dst_rec.get('plan_key') or self._normalize_plan_key(dst_rec.get('title'))
            if not src_key or not dst_key:
                messagebox.showerror("Plan Error", "Unable to resolve plan identifiers.", parent=dialog)
                return

            operation_allowed = self._require_conformer_for_plan_action(
                dialog,
                "merge_plans",
                {
                    "source_plan": {
                        "key": src_key,
                        "title": src_rec.get('title'),
                        "scope": src_rec.get('scope'),
                        "project": src_rec.get('project'),
                        "preview": self._build_plan_preview_text(src_key),
                    },
                    "destination_plan": {
                        "key": dst_key,
                        "title": dst_rec.get('title'),
                        "scope": dst_rec.get('scope'),
                        "project": dst_rec.get('project'),
                        "preview": self._build_plan_preview_text(dst_key),
                    },
                    "rename_to": new_title,
                }
            )
            if not operation_allowed:
                messagebox.showinfo("Merge Cancelled", "Conformer approval is required before merging plans.", parent=dialog)
                return

            success = self._merge_plans_records(src_rec, dst_rec, new_title)
            if success:
                try:
                    refresh_cb()
                except Exception:
                    pass
                dialog.grab_release()
                dialog.destroy()
                messagebox.showinfo("Plans Merged", f"Plans merged into '{new_title}'.", parent=parent)

        ttk.Button(btn_row, text="Merge Plans", command=_confirm_merge, style='Action.TButton').grid(row=0, column=0, sticky=tk.EW, padx=(0,4))
        ttk.Button(btn_row, text="Cancel", command=lambda: (dialog.grab_release(), dialog.destroy()), style='Select.TButton').grid(row=0, column=1, sticky=tk.EW)

    def _merge_plans_records(self, src_rec: Dict[str, Any], dst_rec: Dict[str, Any], new_title: str) -> bool:
        """Perform underlying plan merge operations."""
        try:
            src_key = src_rec.get('plan_key') or self._normalize_plan_key(src_rec.get('title'))
            dst_key = dst_rec.get('plan_key') or self._normalize_plan_key(dst_rec.get('title'))
            if not src_key or not dst_key:
                messagebox.showerror("Plan Error", "Unable to resolve plan identifiers.")
                return False

            dest_path = dst_rec.get('path')
            if not isinstance(dest_path, Path) or not dest_path.exists():
                messagebox.showerror("Plan Error", "Destination plan file missing.")
                return False

            final_title = new_title.strip() or dst_rec.get('title')
            final_key = self._normalize_plan_key(final_title)
            if not final_key:
                messagebox.showerror("Plan Error", "Merged plan name is invalid.")
                return False

            # Rename destination plan if needed
            if final_title != dst_rec.get('title'):
                dest_path = update_todo_file(dest_path, title=final_title)
            set_plan_links(dest_path, [final_key])
            if dst_key != final_key:
                self._replace_plan_key_in_all_todos(dst_key, final_key)
                dst_key = final_key

            # Reassign source plan todos
            self._replace_plan_key_in_all_todos(src_key, dst_key)
            self._archive_plan_file(src_rec)
            return True
        except Exception as exc:
            log_message(f"SETTINGS: Failed to merge plans: {exc}")
            messagebox.showerror("Merge Failed", f"Plan merge failed:\n{exc}")
            return False

    def _find_plan_record_by_key(self, plan_key: str) -> Optional[dict]:
        """Return {'data': todo_dict, 'path': Path} for the plan matching plan_key."""
        if not plan_key:
            return None
        try:
            plan_files = list_todo_files('plans')
        except Exception:
            return None
        for path in plan_files:
            try:
                data = read_todo_file(path)
            except Exception:
                continue
            linked = (data.get('linked_plan') or '').strip()
            if not linked:
                linked = self._normalize_plan_key(data.get('title'))
            if linked == plan_key:
                return {'data': data, 'path': path}
        return None

    def _maybe_auto_complete_plan(self, plan_key: str, parent, refresh_cb=None):
        """Prompt to mark a plan complete when all linked todos are done."""
        plan_key = (plan_key or '').strip()
        if not plan_key:
            return
        open_children, _ = self._collect_plan_children_records(plan_key)
        if open_children:
            return
        plan_record = self._find_plan_record_by_key(plan_key)
        if not plan_record:
            return
        plan_title = plan_record['data'].get('title') or plan_key
        if not messagebox.askyesno(
            "Plan Ready to Complete",
            f"All todos linked to plan '{plan_title}' are complete.\nMark the plan as completed now?",
            parent=parent
        ):
            return
        try:
            move_todo_to_completed(plan_record['path'])
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to mark plan complete:\n{exc}", parent=parent)
            return
        if callable(refresh_cb):
            try:
                refresh_cb()
            except Exception:
                pass
        else:
            try:
                self.refresh_todo_view()
            except Exception:
                pass
        messagebox.showinfo("Plan Completed", f"Plan '{plan_title}' marked complete.", parent=parent)

    def create_ui(self):
        """Create the settings tab UI with side menu and sub-tabs"""
        self.parent.columnconfigure(0, weight=1)
        self.parent.columnconfigure(1, weight=0)
        self.parent.rowconfigure(0, weight=1)

        # Left side: Settings content with sub-tabs
        settings_content_frame = ttk.Frame(self.parent, style='Category.TFrame')
        settings_content_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        settings_content_frame.columnconfigure(0, weight=1)
        settings_content_frame.rowconfigure(1, weight=1)

        # Header with title and refresh buttons
        header_frame = ttk.Frame(settings_content_frame, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, pady=5)
        header_frame.columnconfigure(0, weight=1)

        ttk.Label(header_frame, text="⚙️ Settings",
                 font=("Arial", 14, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT, padx=(0, 10))

        log_message("SETTINGS: Creating Quick Restart button.")
        # Quick Restart button
        quick_restart_btn = ttk.Button(header_frame, text="🚀 Quick Restart",
                  command=self.quick_restart_application,
                  style='Action.TButton')
        quick_restart_btn.pack(side=tk.RIGHT, padx=(5, 0))
        print(f"DEBUG: Quick Restart button created. Command bound to: {quick_restart_btn.cget('command')}")
        log_message(f"SETTINGS: Quick Restart button created. Command bound to: {quick_restart_btn.cget('command')}")

        # Settings tab refresh button
        ttk.Button(header_frame, text="🔄 Refresh Settings",
                  command=self.refresh_settings_tab,
                  style='Select.TButton').pack(side=tk.RIGHT, padx=5)

        # Conformer Events Badge (Phase 1.5D)
        try:
            from conformer_ui_integration import EventsBadge
            self.events_badge = EventsBadge(header_frame)
            self.events_badge.pack(side=tk.RIGHT, padx=5)
            log_message("SETTINGS: EventsBadge added to header")
        except ImportError:
            log_message("SETTINGS: conformer_ui_integration not available, skipping EventsBadge")
        except Exception as e:
            log_message(f"SETTINGS: Error creating EventsBadge: {e}")

        # Sub-tabs notebook
        self.settings_notebook = ttk.Notebook(settings_content_frame)
        self.settings_notebook.grid(row=1, column=0, sticky=tk.NSEW, padx=5, pady=5)

        # General Settings Tab
        self.general_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.general_tab_frame, text="General")
        self.create_general_settings(self.general_tab_frame)

        # Paths Tab
        self.paths_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.paths_tab_frame, text="Paths")
        self.create_path_settings(self.paths_tab_frame)

        # Training Defaults Tab
        self.training_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.training_tab_frame, text="Training Defaults")
        self.create_training_defaults(self.training_tab_frame)

        # Interface Tab
        self.interface_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.interface_tab_frame, text="Interface")
        self.create_ui_settings(self.interface_tab_frame)

        # Tab Manager Tab
        self.tab_manager_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.tab_manager_frame, text="Tab Manager")
        self.create_tab_manager(self.tab_manager_frame)

        # Resources Tab
        self.resources_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.resources_tab_frame, text="Resources")
        self.create_resource_settings(self.resources_tab_frame)

        # Custom Code Tab
        self.custom_code_settings_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.custom_code_settings_frame, text="Custom Code")
        self.create_custom_code_settings(self.custom_code_settings_frame)

        # Debug Tab
        self.debug_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.debug_tab_frame, text="Debug")
        self.create_debug_tab(self.debug_tab_frame)

        # System Blueprints Tab
        self.blueprints_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.blueprints_tab_frame, text="System Blueprints")
        self.create_blueprints_tab(self.blueprints_tab_frame)

        # Help & Guide Tab
        self.help_tab_frame = ttk.Frame(self.settings_notebook)
        self.settings_notebook.add(self.help_tab_frame, text="Help & Guide")
        self.create_help_tab(self.help_tab_frame)

        # Bind sub-tab change event
        self.settings_notebook.bind("<<NotebookTabChanged>>", self._on_sub_tab_changed)

        # Right side: Settings categories menu
        self.create_right_panel(self.parent)

    # --- Plan Template Dialog (shared by Main/Project ToDo) ---
    # Legacy manual plan creation dialog with entry fields for tasks/tests/agents
    # Used by [+Plan] button in TODO manager action buttons row
    def _open_plan_template_dialog(self, project_name: str | None = None):
        dlg = tk.Toplevel(self.root)
        dlg.title('New Plan')
        dlg.geometry('760x560')
        try:
            dlg.transient(self.root); dlg.grab_set()
        except Exception:
            pass

        # Scrollable body container
        container = ttk.Frame(dlg)
        container.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(container, highlightthickness=0)
        vbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.grid(row=0, column=0, sticky=tk.NSEW)
        vbar.grid(row=0, column=1, sticky=tk.NS)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)
        body = ttk.Frame(canvas, padding=10)
        body_id = canvas.create_window((0,0), window=body, anchor='nw')

        # Prepare agent roster for plan rows (use configured roster first)
        available_agents = self._collect_assignable_agents()
        agent_lookup_map: dict[str, dict] = {}
        has_configured_agents = bool(available_agents)
        if has_configured_agents:
            agent_options = ['[Unassigned]']
            agent_lookup_map['[Unassigned]'] = {'name': None, 'role': 'general'}
            seen_labels: dict[str, int] = {}
            for entry in available_agents:
                name = (entry.get('name') or '').strip()
                if not name:
                    continue
                role = (entry.get('role') or 'general').strip().lower()
                base_label = f"{name} ({role.title()})"
                count = seen_labels.get(base_label, 0)
                label = base_label if count == 0 else f"{base_label} #{count+1}"
                seen_labels[base_label] = count + 1
                agent_lookup_map[label] = {'name': name, 'role': role}
                agent_options.append(label)
        else:
            agent_options = ['[No agents configured]']
            agent_lookup_map['[No agents configured]'] = {}

        def _on_body_config(_e=None):
            try:
                canvas.configure(scrollregion=canvas.bbox('all'))
            except Exception:
                pass
        def _on_container_resize(e):
            try:
                canvas.itemconfigure(body_id, width=e.width - vbar.winfo_width())
            except Exception:
                pass
        body.bind('<Configure>', _on_body_config)
        container.bind('<Configure>', _on_container_resize)

        f = body  # Alias for layout
        # Plan name
        ttk.Label(f, text='Plan Name', style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W)
        name_var = tk.StringVar(); ttk.Entry(f, textvariable=name_var).grid(row=0, column=1, sticky=tk.EW)
        # Priority
        ttk.Label(f, text='Priority', style='CategoryPanel.TLabel').grid(row=1, column=0, sticky=tk.W)
        pvar = tk.StringVar(value='medium'); pr = ttk.Frame(f); pr.grid(row=1, column=1, sticky=tk.W)
        ttk.Radiobutton(pr, text='High', value='high', variable=pvar).pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(pr, text='Medium', value='medium', variable=pvar).pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(pr, text='Low', value='low', variable=pvar).pack(side=tk.LEFT, padx=4)
        # Living Project selector (optional)
        project_var = tk.StringVar(value='[None]')
        project_lookup: dict[str, dict] = {}
        lp_manager = None
        active_projects: list[dict[str, Any]] = []
        combo_state = 'readonly'
        preselected_display = '[None]'
        if get_living_project_manager:
            try:
                lp_manager = get_living_project_manager()
                active_projects = lp_manager.list_active_projects() if lp_manager else []
            except Exception as exc:
                log_message(f"SETTINGS: Failed to load Living Projects for plan dialog: {exc}")
                active_projects = []
        if active_projects:
            for proj in active_projects:
                name = proj.get('name') or proj.get('id') or 'Unnamed Project'
                status = (proj.get('status') or '').lower()
                display = name
                if status and status not in ('planning', 'in_progress'):
                    display = f"{display} — {status}"
                if display in project_lookup:
                    display = f"{display} · {proj.get('id', '')[:6]}"
                project_lookup[display] = {'id': proj.get('id'), 'name': name}
        # Ensure current project context is available even if archived/inactive
        if project_name and get_living_project_manager:
            try:
                lp_for_context = lp_manager.load_project(project_name) if lp_manager else None
                if lp_for_context:
                    display = lp_for_context.name or lp_for_context.id
                    if display in project_lookup and project_lookup[display]['id'] != lp_for_context.id:
                        display = f"{display} · {lp_for_context.id[:6]}"
                    project_lookup[display] = {'id': lp_for_context.id, 'name': lp_for_context.name}
                    preselected_display = display
                    combo_state = 'disabled'
            except Exception as exc:
                log_message(f"SETTINGS: Unable to resolve Living Project for plan dialog context: {exc}")
        ttk.Label(f, text='Living Project', style='CategoryPanel.TLabel').grid(row=2, column=0, sticky=tk.W)
        project_row = ttk.Frame(f); project_row.grid(row=2, column=1, sticky=tk.EW, pady=(2,6))
        project_row.columnconfigure(0, weight=1)
        project_values = ['[None]'] + list(project_lookup.keys())
        if preselected_display != '[None]' and preselected_display not in project_values:
            project_values.append(preselected_display)
        if project_values:
            project_var.set(preselected_display if preselected_display != '[None]' else project_values[0])
        project_combo = ttk.Combobox(
            project_row,
            textvariable=project_var,
            values=project_values,
            state=combo_state if project_values and combo_state == 'disabled' else 'readonly'
        )
        project_combo.grid(row=0, column=0, sticky=tk.EW)
        if combo_state == 'disabled':
            project_combo.configure(state='disabled')
        ttk.Label(project_row, text='Link to a Living Project (optional)').grid(row=1, column=0, sticky=tk.W, pady=(2,0))
        # Helper: auto-resize text widget 1..3 lines and hide scrollbar
        def _mk_auto_text(parent, min_lines=1, max_lines=3):
            txt = scrolledtext.ScrolledText(parent, height=min_lines, wrap=tk.WORD, font=('Arial',9), bg='#1e1e1e', fg='#dcdcdc')
            # Hide the visible scrollbar by setting its width to 0; keep wheel working
            try:
                for child in txt.winfo_children():
                    if isinstance(child, tk.Scrollbar):
                        child.configure(width=0)
            except Exception:
                pass
            def _update_height(_e=None):
                try:
                    # Count visual lines (approximate by content lines)
                    text = txt.get('1.0', 'end-1c')
                    lines = max(min_lines, min(max_lines, max(1, text.count('\n') + 1)))
                    if int(txt.cget('height')) != lines:
                        txt.configure(height=lines)
                except Exception:
                    pass
                finally:
                    try:
                        txt.edit_modified(False)
                    except Exception:
                        pass
            try:
                txt.bind('<<Modified>>', _update_height)
            except Exception:
                pass
            return txt

        # Overview
        ttk.Label(f, text='Overview', style='CategoryPanel.TLabel').grid(row=3, column=0, sticky=tk.NW)
        ov = _mk_auto_text(f, 1, 3); ov.grid(row=3, column=1, sticky=tk.NSEW)
        # Objectives
        ttk.Label(f, text='Objectives', style='CategoryPanel.TLabel').grid(row=4, column=0, sticky=tk.NW)
        obj = _mk_auto_text(f, 1, 3); obj.grid(row=4, column=1, sticky=tk.NSEW)
        # Section builder: dynamic single-line entries with + / - controls
        def _mk_section(row_idx: int, label_text: str, examples: list[str]):
            ttk.Label(f, text=label_text, style='CategoryPanel.TLabel').grid(row=row_idx, column=0, sticky=tk.NW, pady=(6,0))
            wrap = ttk.Frame(f); wrap.grid(row=row_idx, column=1, sticky=tk.NSEW, pady=(6,0))
            wrap.columnconfigure(0, weight=1)

            # controls under header
            ctrl = ttk.Frame(wrap)
            ctrl.grid(row=0, column=0, sticky=tk.W)
            rows_frame = ttk.Frame(wrap)
            rows_frame.grid(row=1, column=0, sticky=tk.NSEW)
            rows = []

            def add_row(text: str = '', *, placeholder: bool = False):
                r = ttk.Frame(rows_frame)
                r.columnconfigure(0, weight=1)
                title_entry = ttk.Entry(r)
                title_entry.grid(row=0, column=0, sticky=tk.EW, padx=(0,6), pady=(2,0))
                if text:
                    title_entry.insert(0, text)
                if placeholder and text:
                    try:
                        title_entry.configure(foreground='#888888')
                        title_entry._placeholder = True  # type: ignore[attr-defined]
                    except Exception:
                        pass

                    def _clear_placeholder(_e):
                        try:
                            if getattr(title_entry, '_placeholder', False):
                                title_entry.delete(0, tk.END)
                                title_entry.configure(foreground='#dcdcdc')
                                title_entry._placeholder = False  # type: ignore[attr-defined]
                        except Exception:
                            pass
                    title_entry.bind('<FocusIn>', _clear_placeholder, add='+')

                ttk.Label(r, text='Details', style='CategoryPanel.TLabel').grid(row=1, column=0, sticky=tk.W, pady=(4,0))
                details_txt = scrolledtext.ScrolledText(
                    r,
                    height=3,
                    wrap=tk.WORD,
                    font=('Arial', 9),
                    bg='#1e1e1e',
                    fg='#dcdcdc'
                )
                details_txt.grid(row=2, column=0, sticky=tk.EW, pady=(0,8))
                ttk.Label(r, text='Assigned Agent', style='CategoryPanel.TLabel').grid(row=3, column=0, sticky=tk.W)
                agent_frame = ttk.Frame(r)
                agent_frame.grid(row=4, column=0, sticky=tk.EW, pady=(2,8))
                agent_frame.columnconfigure(0, weight=1)
                agent_var = tk.StringVar()
                default_label = agent_options[0]
                agent_var.set(default_label)
                agent_state = 'readonly' if has_configured_agents else 'disabled'
                agent_combo = ttk.Combobox(
                    agent_frame,
                    textvariable=agent_var,
                    values=agent_options,
                    state=agent_state
                )
                agent_combo.grid(row=0, column=0, sticky=tk.EW)
                agent_status_var = tk.StringVar()

                def _update_agent_status(*_):
                    label = agent_var.get()
                    entry = agent_lookup_map.get(label)
                    if entry and entry.get('name'):
                        role = (entry.get('role') or 'general').strip().lower()
                        agent_status_var.set(f"Assigned to {entry['name']} ({role.title()})")
                    else:
                        if label == '[No agents configured]':
                            agent_status_var.set('No agents configured in the Agents tab yet; add one to enable assignments.')
                        elif label == '[Unassigned]':
                            agent_status_var.set('Select an agent to dispatch this todo or leave unassigned.')
                        else:
                            agent_status_var.set('Previously assigned agent is no longer configured; choose another agent to reassign.')

                agent_combo.bind('<<ComboboxSelected>>', _update_agent_status)
                _update_agent_status()
                ttk.Label(
                    agent_frame,
                    textvariable=agent_status_var,
                    style='CategoryPanel.TLabel',
                    wraplength=360,
                    justify=tk.LEFT
                ).grid(row=1, column=0, sticky=tk.W, pady=(2,0))

                rows.append({
                    'frame': r,
                    'title': title_entry,
                    'details': details_txt,
                    'agent_var': agent_var,
                })
                r.pack(fill=tk.X)

            def remove_row():
                if rows:
                    row = rows.pop()
                    try:
                        frame_ref = row.get('frame')
                        if frame_ref:
                            frame_ref.destroy()
                    except Exception:
                        pass

            ttk.Button(ctrl, text='＋', width=3, command=lambda: add_row('')).pack(side=tk.LEFT, padx=(0,4))
            ttk.Button(ctrl, text='−', width=3, command=remove_row).pack(side=tk.LEFT)

            # Default three entries; first with example placeholder
            add_row(examples[0] if examples else '', placeholder=True)
            add_row('')
            add_row('')

            return rows

        # Build sections
        task_rows = _mk_section(5, 'Tasks', ['Add overview window when a model is selected'])
        wo_rows = _mk_section(6, 'Work Orders', ['Create Popup Window'])
        tests_rows = _mk_section(7, 'Tests', ['Selecting a model shows overview'])
        f.columnconfigure(1, weight=1)
        f.rowconfigure(7, weight=1)
        # Prefill examples
        try:
            ov.insert(tk.END, 'Example: Upgrade Chat interface to show model overview panel.')
            obj.insert(tk.END, '- Improve discoverability\n- Reduce clicks\n- Keep layout responsive')
        except Exception:
            pass
        # Create
        def create_plan():
            try:
                title = (name_var.get() or '').strip()
                if not title:
                    messagebox.showwarning('Missing Plan Name','Please enter a plan name.', parent=dlg); return
                prio = pvar.get()
                from config import create_todo_file, create_project_todo_file
                lp_payload = None
                lp_id = None
                if lp_manager:
                    selection = project_var.get()
                    if selection and selection != '[None]':
                        lp_payload = project_lookup.get(selection)
                if (not lp_payload) and lp_manager and project_name:
                    try:
                        lp_obj = lp_manager.load_project(project_name)
                        if lp_obj:
                            lp_payload = {'id': lp_obj.id, 'name': lp_obj.name}
                    except Exception as exc:
                        log_message(f"SETTINGS: Unable to auto-link plan to Living Project: {exc}")
                if lp_payload and lp_payload.get('id'):
                    lp_id = lp_payload['id']
                def mk(cat, text_, details_text, agent_info: Optional[dict] = None):
                    assigned_agent_name = None
                    assigned_agent_role = None
                    agent_roles_param = None
                    if agent_info:
                        assigned_agent_name = agent_info.get('name')
                        role_val = agent_info.get('role')
                        if role_val:
                            assigned_agent_role = role_val.strip().lower()
                            if assigned_agent_role and assigned_agent_role != 'general':
                                agent_roles_param = [assigned_agent_role]
                    if project_name:
                        path = create_project_todo_file(
                            project_name,
                            cat,
                            text_,
                            prio,
                            details_text,
                            plan=title,
                            living_project=lp_payload,
                            agent_roles=agent_roles_param,
                        )
                    else:
                        path = create_todo_file(
                            cat,
                            text_,
                            prio,
                            details_text,
                            plan=title,
                            living_project=lp_payload,
                            agent_roles=agent_roles_param,
                        )
                    if path and assigned_agent_name:
                        update_todo_file(path, assigned_agent=assigned_agent_name, assigned_agent_role=assigned_agent_role or 'general')
                    return path
                # Plan body summary
                body_parts = [
                    'Overview:\n' + ov.get('1.0', tk.END).strip(),
                    'Objectives:\n' + obj.get('1.0', tk.END).strip(),
                ]
                # Collect non-empty rows; ignore placeholder examples
                def _collect(rows):
                    out = []
                    for row in rows:
                        title_widget = row.get('title')
                        details_widget = row.get('details')
                        title_val = ''
                        details_val = ''
                        try:
                            title_val = (title_widget.get() or '').strip()
                        except Exception:
                            title_val = ''
                        try:
                            details_val = (details_widget.get('1.0', tk.END) or '').strip()
                        except Exception:
                            details_val = ''
                        placeholder_active = False
                        try:
                            placeholder_active = bool(getattr(title_widget, '_placeholder', False))
                        except Exception:
                            placeholder_active = False
                        if not title_val and not details_val:
                            continue
                        if placeholder_active and not details_val:
                            continue
                        agent_label = ''
                        assigned_name = None
                        assigned_role = None
                        try:
                            agent_var = row.get('agent_var')
                            if agent_var:
                                agent_label = agent_var.get()
                        except Exception:
                            agent_label = ''
                        entry = agent_lookup_map.get(agent_label)
                        if entry and entry.get('name'):
                            assigned_name = entry.get('name')
                            assigned_role = (entry.get('role') or 'general').strip().lower()
                        elif agent_label == '[Unassigned]':
                            assigned_role = 'general'
                        out.append({
                            'title': title_val,
                            'details': details_val,
                            'agent': {
                                'name': assigned_name,
                                'role': assigned_role,
                            }
                        })
                    return out
                lines_tasks = _collect(task_rows)
                lines_wo = _collect(wo_rows)
                lines_tests = _collect(tests_rows)

                def _format_section(header: str, entries: list[dict[str, str]], *, numbered: bool = False) -> str:
                    if not entries:
                        return f"{header}:\n-"
                    lines = []
                    for idx, entry in enumerate(entries, 1):
                        label = entry.get('title') or (f'Item {idx}' if numbered else 'Untitled')
                        details = entry.get('details') or ''
                        prefix = f"{idx}. {label}" if numbered else f"- {label}"
                        if details:
                            lines.append(f"{prefix}\n  {details}")
                        else:
                            lines.append(prefix)
                    return f"{header}:\n" + "\n".join(lines)

                body_parts.append(_format_section('Tasks', lines_tasks, numbered=False))
                body_parts.append(_format_section('Work Orders', lines_wo, numbered=True))
                body_parts.append(_format_section('Tests', lines_tests, numbered=False))
                body = '\n\n'.join(body_parts)
                # Plan file
                if project_name:
                    plan_path = create_project_todo_file(project_name, 'plans', f'Plan: {title}', prio, body, plan=title, living_project=lp_payload)
                else:
                    plan_path = create_todo_file('plans', f'Plan: {title}', prio, body, plan=title, living_project=lp_payload)
                if lp_manager and lp_id:
                    try:
                        lp_manager.link_plan(lp_id, str(plan_path))
                    except Exception as exc:
                        log_message(f"SETTINGS: Failed to link plan to Living Project: {exc}")
                # Derived items
                for t in lines_tasks:
                    task_title = t.get('title') or 'Untitled Task'
                    task_details = t.get('details', '')
                    task_path = mk('tasks', f'Plan:{title} | Task: {task_title}', task_details, t.get('agent'))
                    if lp_manager and lp_id and task_path:
                        try:
                            lp_manager.link_todo(lp_id, str(task_path))
                        except Exception as exc:
                            log_message(f"SETTINGS: Failed to link task todo to Living Project: {exc}")
                for i,w in enumerate(lines_wo, 1):
                    wo_title = w.get('title') or f'Work-Order {i}'
                    wo_details = w.get('details', '')
                    wo_path = mk('work_orders', f'Plan:{title} | Work-Order {i}: {wo_title}', wo_details, w.get('agent'))
                    if lp_manager and lp_id and wo_path:
                        try:
                            lp_manager.link_todo(lp_id, str(wo_path))
                        except Exception as exc:
                            log_message(f"SETTINGS: Failed to link work-order todo to Living Project: {exc}")
                for t in lines_tests:
                    test_title = t.get('title') or 'Test'
                    test_details = t.get('details', '')
                    test_path = mk('tests', f'Plan:{title} | Test: {test_title}', test_details, t.get('agent'))
                    if lp_manager and lp_id and test_path:
                        try:
                            lp_manager.link_todo(lp_id, str(test_path))
                        except Exception as exc:
                            log_message(f"SETTINGS: Failed to link test todo to Living Project: {exc}")
                try:
                    # Refresh listings in active popup
                    self.refresh_todo_view()
                except Exception:
                    pass
                dlg.destroy()
            except Exception as e:
                log_message(f'SETTINGS: Error creating plan (dialog): {e}')
                messagebox.showerror('Error', f'Failed to create plan: {e}', parent=dlg)
        footer = ttk.Frame(dlg)
        footer.pack(fill=tk.X, padx=10, pady=(6, 10))
        for col in range(2):  # Phase Sub-Zero-D: Changed from 3 to 2 (removed Ask AI button)
            footer.columnconfigure(col, weight=1)
        # Phase Sub-Zero-D: Removed "Ask AI" button - functionality moved to planner agent dock
        # ttk.Button(
        #     footer,
        #     text='🤖 Ask AI',
        #     command=lambda: self._ask_ai_for_plan(name_var, pvar, ov, obj, project_var, dlg),
        #     style='Select.TButton'
        # ).grid(row=0, column=0, padx=4, sticky=tk.EW)
        ttk.Button(
            footer,
            text='Create Plan',
            style='Action.TButton',
            command=create_plan
        ).grid(row=0, column=0, padx=4, sticky=tk.EW)
        ttk.Button(
            footer,
            text='Cancel',
            style='Select.TButton',
            command=dlg.destroy
        ).grid(row=0, column=1, padx=4, sticky=tk.EW)

    def _create_planner_dock_section(self, parent, project_context: Optional[str] = None):
        """
        Create planner agent dock section in TODO Manager.
        PHASE SUB-ZERO-D: Full agent dock interface with chat, mount, config controls.

        Provides:
        - Session message log display
        - Chat input for direct planner communication
        - Mount/Unmount controls
        - Config access
        - Task queue access
        - Tool configuration
        - Conformer events display

        Args:
            parent: Parent frame (dock pane in PanedWindow)
            project_context: Project name for context-aware planning (optional)

        Returns:
            Container frame with all controls
        """
        import tkinter as tk
        from tkinter import ttk, messagebox

        # Main container
        container = ttk.Frame(parent, style='Category.TFrame')
        container.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Header with collapse control
        header = ttk.Frame(container, style='Category.TFrame')
        header.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(
            header,
            text='Planner Agent Dock',
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT)

        ttk.Button(
            header,
            text='▲ Collapse Dock',
            style='Select.TButton',
            command=lambda: self._open_planner_agent_dock(project_context)
        ).pack(side=tk.RIGHT)

        # ===== SECTION 1: OUTPUT/LOG AREA =====
        # Display planner session messages (last 100)

        output_frame = ttk.Frame(container)
        output_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        output_scroll = ttk.Scrollbar(output_frame, orient=tk.VERTICAL)
        output_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        output_text = tk.Text(
            output_frame,
            height=12,
            wrap=tk.WORD,
            bg='#2b2b2b',
            fg='#d0d0d0',
            font=('Consolas', 9),
            yscrollcommand=output_scroll.set
        )
        output_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        output_scroll.config(command=output_text.yview)

        # Store reference for updates
        self._planner_output_widget = output_text

        # Initial population
        self._update_planner_output()

        # ===== SECTION 2: CHAT INPUT ROW =====

        chat_row = ttk.Frame(container, style='Category.TFrame')
        chat_row.pack(fill=tk.X, pady=(0, 4))
        chat_row.columnconfigure(0, weight=1)

        chat_var = tk.StringVar()
        chat_entry = ttk.Entry(chat_row, textvariable=chat_var)
        chat_entry.grid(row=0, column=0, sticky=tk.EW, padx=(0, 4))

        def send_to_planner():
            msg = chat_var.get().strip()
            if not msg:
                return

            # Add project context if available
            if project_context:
                context_msg = f"[Project: {project_context}] {msg}"
            else:
                context_msg = msg

            success = self._send_to_planner(context_msg)
            if success:
                chat_var.set('')
                # Refresh output immediately
                self._update_planner_output()

        send_btn = ttk.Button(
            chat_row,
            text='Send',
            width=8,
            style='Select.TButton',
            command=send_to_planner
        )
        send_btn.grid(row=0, column=1)

        # Enter key binding
        chat_entry.bind('<Return>', lambda e: send_to_planner())

        # ===== SECTION 3: QUICK CONTROLS ROW =====

        quick_row = ttk.Frame(container, style='Category.TFrame')
        quick_row.pack(fill=tk.X, pady=(0, 4))

        # Conformers button (shows pending conformer events for planner)
        def show_planner_conformers():
            conformer_count = self._get_planner_conformer_count()
            if conformer_count == 0:
                messagebox.showinfo("Planner Conformers", "No pending conformer events for planner agent.")
            else:
                # Show conformer events popup (reuse existing logic)
                self._show_planner_conformers_popup()

        conformer_count = self._get_planner_conformer_count()
        conformer_label = f"Conformers ({conformer_count})" if conformer_count > 0 else "Conformers"

        conformer_btn = ttk.Button(
            quick_row,
            text=conformer_label,
            width=14,
            style='Select.TButton',
            command=show_planner_conformers
        )
        conformer_btn.pack(side=tk.LEFT, padx=(0, 4))

        # Tasks button (open planner task queue)
        def show_planner_tasks():
            self._show_planner_tasks_popup()

        tasks_btn = ttk.Button(
            quick_row,
            text='Tasks',
            width=10,
            style='Select.TButton',
            command=show_planner_tasks
        )
        tasks_btn.pack(side=tk.LEFT, padx=(0, 4))

        # Tools button (open planner tools config)
        def show_planner_tools():
            self._show_planner_tools_config()

        tools_btn = ttk.Button(
            quick_row,
            text='Tools…',
            width=10,
            style='Select.TButton',
            command=show_planner_tools
        )
        tools_btn.pack(side=tk.LEFT, padx=(0, 4))

        # Stop/Unmount All button (right-aligned)
        def stop_all_agents():
            if messagebox.askyesno("Stop All Agents", "Unmount all active agents?"):
                self._unmount_all_agents()
                self._update_planner_output()

        stop_btn = ttk.Button(
            quick_row,
            text='Stop All',
            width=10,
            style='Select.TButton',
            command=stop_all_agents
        )
        stop_btn.pack(side=tk.RIGHT)

        # ===== SECTION 4: MANAGEMENT ROW =====

        mgmt_row = ttk.Frame(container, style='Category.TFrame')
        mgmt_row.pack(fill=tk.X, pady=(0, 0))
        mgmt_row.columnconfigure(0, weight=1)

        # Left cluster: Mount + Config
        left_cluster = ttk.Frame(mgmt_row, style='Category.TFrame')
        left_cluster.grid(row=0, column=0, sticky=tk.W)

        # Mount button
        def mount_planner():
            success, message = self._mount_planner()
            if success:
                messagebox.showinfo("Mount Planner", message)
                self._update_planner_output()
            else:
                messagebox.showerror("Mount Failed", message)

        mount_btn = ttk.Button(
            left_cluster,
            text='⚡ Mount',
            width=10,
            style='Select.TButton',
            command=mount_planner
        )
        mount_btn.pack(side=tk.LEFT, padx=(0, 4))

        # Config button
        def open_planner_config():
            self._open_planner_config()

        config_btn = ttk.Button(
            left_cluster,
            text='⚙️ Config',
            width=10,
            style='Select.TButton',
            command=open_planner_config
        )
        config_btn.pack(side=tk.LEFT, padx=(0, 4))

        # Right cluster: Unmount
        right_cluster = ttk.Frame(mgmt_row, style='Category.TFrame')
        right_cluster.grid(row=0, column=1, sticky=tk.E)

        # Unmount button
        def unmount_planner():
            if messagebox.askyesno("Unmount Planner", "Unmount planner agent?"):
                success, message = self._unmount_planner()
                if success:
                    messagebox.showinfo("Unmount Planner", message)
                    self._update_planner_output()
                else:
                    messagebox.showwarning("Unmount", message)

        unmount_btn = ttk.Button(
            right_cluster,
            text='Unmount',
            width=10,
            style='Select.TButton',
            command=unmount_planner
        )
        unmount_btn.pack(side=tk.LEFT)

        # ===== SECTION 5: STATUS BAR =====

        status_row = ttk.Frame(container, style='Category.TFrame')
        status_row.pack(fill=tk.X, pady=(4, 0))

        # Mount status indicator
        mount_status = self._get_planner_mount_status()
        status_text = "● Planner Mounted" if mount_status else "○ Planner Not Mounted"

        status_label = ttk.Label(
            status_row,
            text=status_text,
            style='Config.TLabel',
            foreground='#00ff00' if mount_status else '#888888'
        )
        status_label.pack(side=tk.LEFT)

        # Store reference for updates
        self._planner_status_label = status_label

        # Start session log polling
        self._start_planner_log_refresh()

        return container

    def _toggle_planner_dock_expansion(self):
        """Toggle the planner dock expansion state within the TODO popup."""
        if not hasattr(self, '_planner_dock_expanded'):
            self._planner_dock_expanded = False
        self._planner_dock_expanded = not self._planner_dock_expanded
        log_message(f"SETTINGS: Planner dock expansion toggled: expanded={self._planner_dock_expanded}")

    def _expand_planner_dock(self):
        """Force expand the planner dock within the TODO popup."""
        self._planner_dock_expanded = True
        log_message("SETTINGS: Planner dock expanded via expand button")

    @debug_ui_event(_settings_debug_logger)
    def _open_planner_agent_dock(self, project_name: Optional[str] = None):
        """
        Phase Sub-Zero-D: Toggle planner agent dock in TODO popup.
        Creates/shows collapsible agent dock for plan creation using planner agent.

        Args:
            project_name: Optional project context for the planner
        """
        # Set flag to trigger dock visibility in TODO popup
        # The dock is embedded in the popup itself, not a separate window
        if not hasattr(self, '_planner_dock_visible'):
            self._planner_dock_visible = False
            self._planner_project_context = None

        # Toggle visibility
        self._planner_dock_visible = not self._planner_dock_visible
        self._planner_project_context = project_name

        # Force expansion on first open
        if self._planner_dock_visible and not hasattr(self, '_planner_dock_expanded'):
            self._planner_dock_expanded = True

        log_message(f"SETTINGS: Planner dock toggled: visible={self._planner_dock_visible}, project={project_name}")

        # CRITICAL FIX: Actually refresh the popup to show/hide dock
        if hasattr(self, 'todo_popup_active') and self.todo_popup_active:
            # Store reference to active popup window
            active_popup = getattr(self, '_active_todo_popup_window', None)

            if active_popup:
                try:
                    # Close current popup
                    active_popup.destroy()
                    log_message("SETTINGS: Closed TODO popup for dock refresh")
                except Exception as e:
                    log_message(f"SETTINGS: Error closing popup: {e}")

                # Reopen with new dock state
                try:
                    if project_name:
                        self.show_project_todo_popup(project_name)
                    else:
                        self.show_main_todo_popup()
                    log_message(f"SETTINGS: Reopened TODO popup with dock_visible={self._planner_dock_visible}")
                except Exception as e:
                    log_message(f"SETTINGS: Error reopening popup: {e}")
            else:
                log_message("SETTINGS: No active popup window reference found")
        else:
            # Popup not open yet - dock will show when opened
            log_message("SETTINGS: Popup not active, dock will show on next open")

    # ===== PHASE SUB-ZERO-D: PLANNER DOCK BACKEND WIRING METHODS =====

    def _get_chat_interface_tab(self):
        """
        Navigate to chat_interface_tab for planner communication.

        Returns:
            ChatInterfaceTab instance or None if not found
        """
        try:
            # Navigate: self → main window → custom_code_tab → chat_interface_tab
            root = self.root  # Main GUI window
            if hasattr(root, 'custom_code_tab'):
                custom_code = root.custom_code_tab
                if hasattr(custom_code, 'chat_interface_tab'):
                    return custom_code.chat_interface_tab
        except Exception as e:
            if _settings_debug_logger:
                _settings_debug_logger.error("Failed to get chat_interface_tab", exc_info=e)
        return None

    def _get_planner_session(self):
        """
        Get planner agent session dict from chat_interface_tab.

        Returns:
            dict with keys: log, context, working
            or None if session doesn't exist
        """
        try:
            chat_interface = self._get_chat_interface_tab()
            if chat_interface and hasattr(chat_interface, '_agents_sessions'):
                return chat_interface._agents_sessions.get('planner', None)
        except Exception as e:
            if _settings_debug_logger:
                _settings_debug_logger.error("Failed to get planner session", exc_info=e)
        return None

    def _send_to_planner(self, message: str) -> bool:
        """
        Send message to planner agent via chat_interface_tab.

        Args:
            message: Text message to send to planner

        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            chat_interface = self._get_chat_interface_tab()
            if not chat_interface:
                log_message("PLANNER_DOCK: Failed to get chat_interface_tab")
                return False

            # Check if planner is mounted
            if not self._get_planner_mount_status():
                log_message("PLANNER_DOCK: Cannot send message - planner not mounted")
                messagebox.showwarning(
                    "Planner Not Mounted",
                    "Please mount the planner agent before sending messages."
                )
                return False

            # Send message via chat interface
            chat_interface.send_agent_message('planner', message)

            if _settings_debug_logger:
                _settings_debug_logger.info(
                    "Sent message to planner",
                    message_preview=message[:50] + "..." if len(message) > 50 else message
                )

            return True

        except Exception as e:
            log_message(f"PLANNER_DOCK: Failed to send message to planner: {e}")
            if _settings_debug_logger:
                _settings_debug_logger.error("Failed to send message to planner", exc_info=e)
            return False

    def _update_planner_output(self):
        """
        Update planner dock output widget with latest session messages.

        Reads last 100 messages from agent_sessions['planner'] and displays them.
        """
        try:
            if not hasattr(self, '_planner_output_widget') or not self._planner_output_widget:
                return

            output = self._planner_output_widget
            session = self._get_planner_session()

            # Clear current content
            output.delete('1.0', tk.END)

            if not session:
                output.insert(tk.END, "[No planner session active]\n\n")
                output.insert(tk.END, "Configure planner agent in Agents tab and mount it to start a session.")
                return

            log_entries = session.get('log', [])

            if not log_entries:
                output.insert(tk.END, "[Session active - no messages yet]\n\n")
                output.insert(tk.END, "Send a message to the planner agent to begin planning.")
                return

            # Display last 100 log entries
            for entry in log_entries[-100:]:
                role = entry.get('role', 'system')
                text = entry.get('text', '')

                # Format message with role prefix
                output.insert(tk.END, f"[{role.upper()}] {text}\n\n")

            # Auto-scroll to bottom
            output.see(tk.END)

            # Update status label if exists
            if hasattr(self, '_planner_status_label'):
                mount_status = self._get_planner_mount_status()
                status_text = "● Planner Mounted" if mount_status else "○ Planner Not Mounted"
                self._planner_status_label.config(
                    text=status_text,
                    foreground='#00ff00' if mount_status else '#888888'
                )

        except Exception as e:
            log_message(f"PLANNER_DOCK: Failed to update output: {e}")
            if _settings_debug_logger:
                _settings_debug_logger.error("Failed to update planner output", exc_info=e)

    def _start_planner_log_refresh(self):
        """
        Start periodic polling to refresh planner session log.

        Polls every 2 seconds for new messages and updates output widget.
        """
        if not hasattr(self, '_planner_refresh_job'):
            self._planner_refresh_job = None

        def poll():
            try:
                self._update_planner_output()
            except Exception as e:
                log_message(f"PLANNER_DOCK: Poll update failed: {e}")

            # Schedule next poll
            if hasattr(self, '_planner_refresh_job'):
                self._planner_refresh_job = self.root.after(2000, poll)

        # Start polling
        poll()

    def _stop_planner_log_refresh(self):
        """Stop planner session log polling."""
        if hasattr(self, '_planner_refresh_job') and self._planner_refresh_job:
            self.root.after_cancel(self._planner_refresh_job)
            self._planner_refresh_job = None

    def _mount_planner(self) -> tuple[bool, str]:
        """
        Mount planner agent (spawn server or connect to ollama).

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # Get agents_tab reference
            root = self.root
            if not hasattr(root, 'custom_code_tab'):
                return False, "Failed to access Custom Code tab"

            custom_code = root.custom_code_tab
            if not hasattr(custom_code, 'agents_tab'):
                return False, "Failed to access Agents tab"

            agents_tab = custom_code.agents_tab

            # Check if planner is configured
            if not hasattr(agents_tab, 'agent_configs'):
                return False, "Agent configs not loaded"

            planner_config = agents_tab.agent_configs.get('planner')

            if not planner_config:
                return False, (
                    "Planner not configured.\n\n"
                    "Please go to Custom Code → Agents tab and configure a variant for the planner agent."
                )

            variant = planner_config.get('variant', '').strip()
            if not variant or variant.lower() == 'not selected':
                # Check for override
                if not (planner_config.get('gguf_override') or planner_config.get('ollama_tag_override')):
                    return False, (
                        "No variant selected for planner.\n\n"
                        "Please go to Custom Code → Agents tab and select a variant for the planner agent."
                    )

            # Mount via agents_tab
            agents_tab._mount_agent_from_card('planner')

            if _settings_debug_logger:
                _settings_debug_logger.info("Planner mount initiated", variant=variant)

            return True, "Planner agent mount initiated. Check output log for status."

        except Exception as e:
            log_message(f"PLANNER_DOCK: Failed to mount planner: {e}")
            if _settings_debug_logger:
                _settings_debug_logger.error("Failed to mount planner", exc_info=e)
            return False, f"Mount failed: {str(e)}"

    def _unmount_planner(self) -> tuple[bool, str]:
        """
        Unmount planner agent (stop server).

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            chat_interface = self._get_chat_interface_tab()
            if not chat_interface:
                return False, "Failed to access chat interface"

            # Call unmount
            chat_interface._unmount_agent('planner')

            if _settings_debug_logger:
                _settings_debug_logger.info("Planner unmounted")

            return True, "Planner agent unmounted successfully."

        except Exception as e:
            log_message(f"PLANNER_DOCK: Failed to unmount planner: {e}")
            if _settings_debug_logger:
                _settings_debug_logger.error("Failed to unmount planner", exc_info=e)
            return False, f"Unmount failed: {str(e)}"

    def _unmount_all_agents(self):
        """Unmount all active agents."""
        try:
            chat_interface = self._get_chat_interface_tab()
            if chat_interface and hasattr(chat_interface, '_agents_mounted_set'):
                mounted = list(chat_interface._agents_mounted_set)
                for agent_name in mounted:
                    chat_interface._unmount_agent(agent_name)
        except Exception as e:
            log_message(f"PLANNER_DOCK: Failed to unmount all agents: {e}")

    def _get_planner_mount_status(self) -> bool:
        """
        Check if planner agent is currently mounted.

        Returns:
            bool: True if planner is mounted, False otherwise
        """
        try:
            chat_interface = self._get_chat_interface_tab()
            if not chat_interface:
                return False

            if hasattr(chat_interface, '_agents_mounted_set'):
                return 'planner' in chat_interface._agents_mounted_set

            return False

        except Exception as e:
            if _settings_debug_logger:
                _settings_debug_logger.error("Failed to get planner mount status", exc_info=e)
            return False

    def _open_planner_config(self):
        """Open planner agent configuration dialog (from agents_tab)."""
        try:
            root = self.root
            if hasattr(root, 'custom_code_tab'):
                custom_code = root.custom_code_tab
                if hasattr(custom_code, 'agents_tab'):
                    # Switch to Custom Code tab → Agents sub-tab
                    if hasattr(root, 'notebook'):
                        # Find Custom Code tab index
                        for i in range(root.notebook.index('end')):
                            if root.notebook.tab(i, 'text').strip() == '💻 Custom Code':
                                root.notebook.select(i)
                                break

                    # Switch to Agents sub-tab within Custom Code
                    if hasattr(custom_code, 'sub_notebook'):
                        for i in range(custom_code.sub_notebook.index('end')):
                            if custom_code.sub_notebook.tab(i, 'text').strip() == '🤖 Agents':
                                custom_code.sub_notebook.select(i)
                                break

                    log_message("PLANNER_DOCK: Switched to Agents tab for planner configuration")

        except Exception as e:
            log_message(f"PLANNER_DOCK: Failed to open planner config: {e}")
            if _settings_debug_logger:
                _settings_debug_logger.error("Failed to open planner config", exc_info=e)

    def _show_planner_tools_config(self):
        """Open planner tools configuration dialog."""
        try:
            root = self.root
            if hasattr(root, 'custom_code_tab'):
                custom_code = root.custom_code_tab
                if hasattr(custom_code, '_show_agent_tools_popup'):
                    custom_code._show_agent_tools_popup('planner')
                else:
                    messagebox.showinfo(
                        "Planner Tools",
                        "Planner tools are configured via planner_skilled.json.\n\n"
                        "Available tools:\n"
                        "- read_plans\n"
                        "- create_plan\n"
                        "- link_plan_to_todo\n"
                        "- estimate_duration\n"
                        "- add_todo_to_plan"
                    )
        except Exception as e:
            log_message(f"PLANNER_DOCK: Failed to show tools config: {e}")

    def _get_planner_conformer_count(self) -> int:
        """
        Get count of pending conformer events for planner agent.

        Returns:
            int: Number of pending conformer events
        """
        try:
            chat_interface = self._get_chat_interface_tab()
            if not chat_interface:
                return 0

            if hasattr(chat_interface, '_pending_conformer_events'):
                conf_map = chat_interface._pending_conformer_events
                planner_events = conf_map.get('planner', [])
                return len(planner_events)

            return 0

        except Exception as e:
            if _settings_debug_logger:
                _settings_debug_logger.error("Failed to get conformer count", exc_info=e)
            return 0

    def _show_planner_conformers_popup(self):
        """Show conformer events popup for planner agent."""
        try:
            root = self.root
            if hasattr(root, 'custom_code_tab'):
                custom_code = root.custom_code_tab
                if hasattr(custom_code, '_show_conformer_popup'):
                    custom_code._show_conformer_popup('planner')
        except Exception as e:
            log_message(f"PLANNER_DOCK: Failed to show conformers popup: {e}")

    def _show_planner_tasks_popup(self):
        """Show task queue popup for planner agent."""
        try:
            root = self.root
            if hasattr(root, 'custom_code_tab'):
                custom_code = root.custom_code_tab
                if hasattr(custom_code, '_show_agent_tasks_popup'):
                    custom_code._show_agent_tasks_popup('planner')
        except Exception as e:
            log_message(f"PLANNER_DOCK: Failed to show tasks popup: {e}")

    # ===== END PHASE SUB-ZERO-D PLANNER DOCK METHODS =====

    def _get_active_agent(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve the active agent from agents_tab.

        Returns:
            Dict with agent details (name, type, variant, etc.) or None if no agent active
        """
        try:
            if not self.tab_instances or 'Custom Code' not in self.tab_instances:
                log_message("SETTINGS: Custom Code tab not available for agent retrieval")
                return None

            custom_code_tab = self.tab_instances['Custom Code']
            if not hasattr(custom_code_tab, 'agents_tab'):
                log_message("SETTINGS: Agents tab not available in Custom Code tab")
                return None

            agents_tab = custom_code_tab.agents_tab

            # Get currently mounted/active agent
            if hasattr(agents_tab, '_current_chat_agent') and agents_tab._current_chat_agent:
                agent_info = {
                    'name': agents_tab._current_chat_agent,
                    'source': 'mounted_agent'
                }
                log_message(f"SETTINGS: Retrieved active agent: {agent_info['name']}")
                return agent_info

            # Fallback: check if any agent is selected in the agents list
            if hasattr(agents_tab, 'agent_tree'):
                selected = agents_tab.agent_tree.selection()
                if selected:
                    item = selected[0]
                    values = agents_tab.agent_tree.item(item, 'values')
                    if values:
                        agent_info = {
                            'name': values[0] if len(values) > 0 else 'Unknown',
                            'source': 'selected_agent'
                        }
                        log_message(f"SETTINGS: Retrieved selected agent: {agent_info['name']}")
                        return agent_info

            log_message("SETTINGS: No active or selected agent found")
            return None

        except Exception as exc:
            log_message(f"SETTINGS: Error retrieving active agent: {exc}")
            return None

    def _ask_ai_for_todo(self, title_var, details_text, category_var, project_var, parent_dlg):
        """
        Open AI assistant dialog for TODO creation.

        Args:
            title_var: tk.StringVar for title
            details_text: scrolledtext.ScrolledText widget for details
            category_var: tk.StringVar for category
            project_var: tk.StringVar for project selection
            parent_dlg: Parent dialog window
        """
        if not AI_ASSISTANT_AVAILABLE:
            messagebox.showwarning(
                "Feature Unavailable",
                "AI assistant dialog is not available.",
                parent=parent_dlg
            )
            return

        def apply_suggestion(suggestion: Dict[str, Any]):
            """Apply AI suggestion to the TODO form."""
            try:
                if 'title' in suggestion:
                    title_var.set(suggestion['title'])
                if 'details' in suggestion:
                    details_text.delete('1.0', tk.END)
                    details_text.insert('1.0', suggestion['details'])
                if 'category' in suggestion:
                    category_var.set(suggestion['category'])
                log_message("SETTINGS: Applied AI suggestion to TODO form")
            except Exception as exc:
                log_message(f"SETTINGS: Error applying AI suggestion to TODO: {exc}")
                messagebox.showerror(
                    "Apply Error",
                    f"Failed to apply suggestion: {exc}",
                    parent=parent_dlg
                )

        # Get initial context from existing form data
        initial_context = title_var.get()
        if not initial_context:
            initial_context = details_text.get('1.0', tk.END).strip()

        try:
            show_ai_assistant(
                parent=parent_dlg,
                mode='todo',
                get_active_agent_fn=self._get_active_agent,
                callback=apply_suggestion,
                initial_context=initial_context if initial_context else None
            )
        except Exception as exc:
            log_message(f"SETTINGS: Error opening AI assistant for TODO: {exc}")
            messagebox.showerror(
                "AI Assistant Error",
                f"Failed to open AI assistant: {exc}",
                parent=parent_dlg
            )

    def _ask_ai_for_plan(self, name_var, priority_var, overview_text, objectives_text, project_var, parent_dlg):
        """
        Open AI assistant dialog for Plan creation.

        Args:
            name_var: tk.StringVar for plan name
            priority_var: tk.StringVar for priority
            overview_text: scrolledtext.ScrolledText widget for overview
            objectives_text: scrolledtext.ScrolledText widget for objectives
            project_var: tk.StringVar for project selection
            parent_dlg: Parent dialog window
        """
        if not AI_ASSISTANT_AVAILABLE:
            messagebox.showwarning(
                "Feature Unavailable",
                "AI assistant dialog is not available.",
                parent=parent_dlg
            )
            return

        def apply_suggestion(suggestion: Dict[str, Any]):
            """Apply AI suggestion to the Plan form."""
            try:
                if 'name' in suggestion:
                    name_var.set(suggestion['name'])
                if 'overview' in suggestion:
                    overview_text.delete('1.0', tk.END)
                    overview_text.insert('1.0', suggestion['overview'])
                if 'objectives' in suggestion:
                    objectives_text.delete('1.0', tk.END)
                    objectives_text.insert('1.0', suggestion['objectives'])
                if 'priority' in suggestion:
                    priority_var.set(suggestion['priority'])
                log_message("SETTINGS: Applied AI suggestion to Plan form")
            except Exception as exc:
                log_message(f"SETTINGS: Error applying AI suggestion to Plan: {exc}")
                messagebox.showerror(
                    "Apply Error",
                    f"Failed to apply suggestion: {exc}",
                    parent=parent_dlg
                )

        # Get initial context from existing form data
        initial_context = name_var.get()
        if not initial_context:
            initial_context = overview_text.get('1.0', tk.END).strip()

        try:
            show_ai_assistant(
                parent=parent_dlg,
                mode='plan',
                get_active_agent_fn=self._get_active_agent,
                callback=apply_suggestion,
                initial_context=initial_context if initial_context else None
            )
        except Exception as exc:
            log_message(f"SETTINGS: Error opening AI assistant for Plan: {exc}")
            messagebox.showerror(
                "AI Assistant Error",
                f"Failed to open AI assistant: {exc}",
                parent=parent_dlg
            )

    def _on_sub_tab_changed(self, event):
        """Switch between help menu and terminal based on selected sub-tab."""
        selected_tab_index = self.settings_notebook.index(self.settings_notebook.select())
        selected_tab_text = self.settings_notebook.tab(selected_tab_index, "text")

        # Auto-enable Arrow reordering when opening Tab Manager (without popups)
        if selected_tab_text == "Tab Manager":
            try:
                self._suppress_reorder_popup = True
                self.reorder_mode.set('arrow')
                self._on_reorder_mode_changed()
                # Ensure tree reflects live tab instances (panels) once Tab Manager is shown
                try:
                    self.refresh_tabs_tree()
                except Exception:
                    pass
            except Exception:
                pass
            finally:
                self._suppress_reorder_popup = False

        if selected_tab_text == "Debug":
            self.help_menu_frame.grid_remove()
            # Lazy-initialize terminal when Debug is selected
            if not self.terminal_initialized:
                self.create_terminal_ui(self.terminal_frame)
                self.terminal_initialized = True
            self.terminal_frame.grid()
        else:
            # Destroy terminal contents to stop background threads
            try:
                # Properly terminate terminal before destroying widget
                if hasattr(self, 'terminal') and self.terminal is not None:
                    try:
                        # Close the subprocess cleanly
                        if hasattr(self.terminal, '_popen') and self.terminal._popen:
                            self.terminal._popen.terminate()
                            self.terminal._popen.wait(timeout=1)
                    except Exception as e:
                        log_message(f"SETTINGS: Terminal termination error (expected): {e}")

                # Now destroy widgets
                for child in self.terminal_frame.winfo_children():
                    child.destroy()

                # Clear terminal reference
                self.terminal = None
                self.terminal_widget = None
            except Exception as e:
                log_message(f"SETTINGS: Terminal cleanup error: {e}")

            self.terminal_initialized = False
            self.terminal_frame.grid_remove()
            self.help_menu_frame.grid()

    def create_terminal_ui(self, parent):
        """Creates the terminal interface using tkterminal library."""
        try:
            from tkterminal import Terminal
        except ImportError:
            error_label = ttk.Label(
                parent,
                text="Error: 'tkterminal' library not found.\nPlease install it by running: pip install tkterminal",
                foreground="red",
                wraplength=300
            )
            error_label.pack(pady=20, padx=10)
            return

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Header with reset button
        header = ttk.Frame(parent)
        header.grid(row=0, column=0, sticky=tk.EW, padx=5, pady=5)
        ttk.Button(header, text="🔁 Reset Terminal", command=lambda: self.reset_terminal(parent), style='Select.TButton').pack(side=tk.LEFT)

        self.terminal = Terminal(parent, pady=5, padx=5)
        self.terminal.shell = True
        self.terminal_widget = self.terminal
        self.terminal_widget.grid(row=1, column=0, sticky='nsew')

        # Use main-thread safe scheduling for terminal commands
        try:
            self.root.after(0, lambda: self.terminal_widget.run_command(f"cd {DATA_DIR} && clear"))
            self.root.after(10, lambda: self.terminal_widget.run_command("echo 'Welcome to the in-house terminal!'"))
            self.root.after(20, lambda: self.terminal_widget.run_command(f"echo 'Working directory: $(pwd)'"))
        except Exception as e:
            log_message(f"SETTINGS: Terminal init scheduling error: {e}")

    def reset_terminal(self, parent):
        """Destroy and recreate the terminal widget to clear state and stop any background threads."""
        try:
            # Properly terminate terminal subprocess before destroying
            if hasattr(self, 'terminal') and self.terminal is not None:
                try:
                    if hasattr(self.terminal, '_popen') and self.terminal._popen:
                        self.terminal._popen.terminate()
                        self.terminal._popen.wait(timeout=1)
                except Exception as e:
                    log_message(f"SETTINGS: Terminal reset termination error: {e}")

            # Destroy widgets
            for child in parent.winfo_children():
                child.destroy()

            # Clear references
            self.terminal = None
            self.terminal_widget = None
        except Exception as e:
            log_message(f"SETTINGS: Terminal reset error: {e}")

        # Recreate terminal UI
        self.create_terminal_ui(parent)



    def create_right_panel(self, parent):
        """Create the right-side panel which can contain either the help menu or the terminal."""
        self.right_panel = ttk.Frame(parent)
        self.right_panel.grid(row=0, column=1, sticky=tk.NSEW, padx=10, pady=10)
        self.right_panel.columnconfigure(0, weight=1)
        self.right_panel.rowconfigure(0, weight=1)

        # --- Help Menu Frame ---
        self.help_menu_frame = ttk.Frame(self.right_panel, style='Category.TFrame')
        self.help_menu_frame.grid(row=0, column=0, sticky='nsew')
        self.help_menu_frame.columnconfigure(0, weight=1)
        self.help_menu_frame.rowconfigure(1, weight=1)
        self.help_menu_frame.rowconfigure(2, weight=0)

        ttk.Label(self.help_menu_frame, text="🆘 Help Menu",
                 font=("Arial", 11, "bold"), style='CategoryPanel.TLabel').grid(
            row=0, column=0, pady=5, sticky=tk.W, padx=5
        )

        self.help_paned = ttk.PanedWindow(self.help_menu_frame, orient=tk.VERTICAL)
        self.help_paned.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)

        tree_container = ttk.Frame(self.help_paned)
        self.help_paned.add(tree_container, weight=1)
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)

        tree_scroll = ttk.Scrollbar(tree_container, orient="vertical")
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.help_tree = ttk.Treeview(
            tree_container,
            yscrollcommand=tree_scroll.set,
            selectmode='browse',
            height=15
        )
        self.help_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.help_tree.yview)

        self.help_tree.heading('#0', text='Topic')
        self.help_tree.tag_configure('main_tab', font=('Arial', 10, 'bold'))
        self.help_tree.bind('<<TreeviewSelect>>', self.on_help_topic_select)
        
        self.populate_help_tree()

        # Help text pane is created but not added until a topic is selected
        self.help_text_frame = ttk.Frame(self.help_paned, style='Category.TFrame')
        self.help_text_frame.columnconfigure(0, weight=1)
        self.help_text_frame.rowconfigure(0, weight=1)

        self.help_display = scrolledtext.ScrolledText(
            self.help_text_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Arial", 9),
            bg="#1e1e1e", fg="#d4d4d4", relief='flat', padx=5, pady=5
        )
        self.help_display.grid(row=0, column=0, sticky='nsew')

        # --- ToDo List Section (as a pane under the help content) ---
        self.todo_section = ttk.Frame(self.help_paned, style='Category.TFrame')
        self.help_paned.add(self.todo_section, weight=1)
        self.todo_section.columnconfigure(0, weight=1)

        # Header with dynamic counts, centered
        # Todo header with separate lines for better layout
        self.todo_counts_var = tk.StringVar(value="Tasks: 0 | Bugs: 0 | Work-Orders: 0 | Notes: 0 | Completed: 0")
        self.todo_priority_var = tk.StringVar(value="Priority: High 0 | Medium 0 | Low 0")
        header_row = ttk.Frame(self.todo_section, style='Category.TFrame')
        header_row.grid(row=0, column=0, sticky=tk.EW, pady=(4, 0))
        header_row.columnconfigure(0, weight=0)
        header_row.columnconfigure(1, weight=1)

        # Show-on-launch checkbox (no label)
        self.todo_show_on_launch = tk.BooleanVar(value=self.settings.get('todo_show_on_launch', False))
        cb = ttk.Checkbutton(header_row, variable=self.todo_show_on_launch, command=self._on_todo_show_on_launch_changed)
        cb.grid(row=0, column=0, rowspan=2, sticky=tk.W, padx=(0,8))

        # Two-line header for better fit
        ttk.Label(header_row, textvariable=self.todo_counts_var, font=("Arial", 10, "bold"), style='CategoryPanel.TLabel', anchor='center').grid(row=0, column=1, sticky=tk.EW)
        ttk.Label(header_row, textvariable=self.todo_priority_var, font=("Arial", 9), style='CategoryPanel.TLabel', anchor='center').grid(row=1, column=1, sticky=tk.EW)

        # Project selector row (manual override for project view)
        selector_row = ttk.Frame(self.todo_section, style='Category.TFrame')
        selector_row.grid(row=1, column=0, sticky=tk.EW, pady=(10, 6))
        selector_row.columnconfigure(1, weight=1)
        ttk.Label(selector_row, text="Project View", style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W, padx=(0, 6))
        selector_values, selector_map = self._get_todo_project_selector_data()
        self.todo_project_selector_map = selector_map
        default_selector_value = selector_values[0] if selector_values else "[Main]"
        self.todo_project_var = tk.StringVar(value=default_selector_value)
        project_combo = ttk.Combobox(
            selector_row,
            textvariable=self.todo_project_var,
            values=selector_values,
            state='readonly'
        )
        project_combo.grid(row=0, column=1, sticky=tk.EW, padx=(0, 6))
        ttk.Button(
            selector_row,
            text="Open Project ToDo",
            style='Select.TButton',
            command=self._open_project_todo_from_main_selector
        ).grid(row=0, column=2, sticky=tk.E)

        # Action buttons for embedded view (help pane)
        buttons_row_main = ttk.Frame(self.todo_section)
        buttons_row_main.grid(row=2, column=0, sticky=tk.EW, pady=(0, 8))
        for col in range(4):
            buttons_row_main.columnconfigure(col, weight=1)
        self.todo_btn_create = ttk.Button(buttons_row_main, text="➕ Create Todo", command=self.todo_create, style='Action.TButton')
        self.todo_btn_create.grid(row=0, column=0, padx=3, sticky=tk.EW)
        self.todo_btn_mark = ttk.Button(buttons_row_main, text="✔ Mark Complete", command=self.todo_mark_complete, style='Select.TButton')
        self.todo_btn_mark.grid(row=0, column=1, padx=3, sticky=tk.EW)
        self.todo_btn_edit = ttk.Button(buttons_row_main, text="✏️ Edit Todo", command=self.todo_edit, style='Select.TButton')
        self.todo_btn_edit.grid(row=0, column=2, padx=3, sticky=tk.EW)
        self.todo_btn_delete = ttk.Button(buttons_row_main, text="🗑 Delete Todo", command=self.todo_delete, style='Select.TButton')
        self.todo_btn_delete.grid(row=0, column=3, padx=3, sticky=tk.EW)

        # Tree for Tasks/Bugs/Completed with checkbox-like glyphs
        tree_wrap = ttk.Frame(self.todo_section)
        tree_wrap.grid(row=3, column=0, sticky='nsew')
        self.todo_section.rowconfigure(3, weight=2)
        tree_scroll = ttk.Scrollbar(tree_wrap, orient="vertical")
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.todo_tree = ttk.Treeview(tree_wrap, columns=("done",), show='tree headings')
        self.todo_tree.heading('#0', text='Item')
        self.todo_tree.heading('done', text='Done')
        self.todo_tree.column('done', width=60, anchor=tk.CENTER, stretch=False)
        self.todo_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.todo_tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.config(command=self.todo_tree.yview)
        # Styles for completed
        self.todo_tree.tag_configure('completed', foreground='#8a8a8a', font=('Arial', 9, 'italic'))
        # Bind click to toggle checkbox in 'done' column
        self.todo_tree.bind('<Button-1>', self._on_todo_click, add=True)

        # Initialize storage and populate
        if not hasattr(self, 'todos'):
            self.todos = { 'tasks': [], 'bugs': [], 'work_orders': [], 'notes': [], 'completed': [] }
        else:
            # Backfill new categories if missing
            self.todos.setdefault('work_orders', [])
            self.todos.setdefault('notes', [])
        self.todo_tree.bind('<<TreeviewSelect>>', self._on_todo_selection_changed)
        self._wire_todo_button_hover()
        self.refresh_todo_view()

        # --- Terminal Frame (created here, but hidden) ---
        self.terminal_frame = ttk.Frame(self.right_panel, style='Category.TFrame')
        self.terminal_frame.grid(row=0, column=0, sticky='nsew')
        # Do not initialize the terminal yet; wait until Debug tab is selected
        self.terminal_frame.grid_remove() # Hide it initially

    def populate_help_tree(self):
        """Populate the help tree with application structure and help text."""
        for item in self.help_tree.get_children():
            self.help_tree.delete(item)

        self.help_structure = {
            "Automation Guide": {
                "description": "How to drive common workflows with minimal clicks using Quick Actions, saved orders, and defaults.",
                "sub_tabs": {
                    "Quick Actions": "Use ⚙ at bottom-left in Chat to access: Working Dir, Tools, Think Time (one-shot), Mode, Prompt/Schema, Temperature (Manual/Auto), and ToDo. The icon grid wraps and auto-hides when clicking away.",
                    "Indicators": "Next to ⚙: ⏱ ThinkTime pending • 📂 Working dir (hover shows path) • 🔧 Enabled tools (hover lists) • 🌡 Temp (value + Manual/Auto) • 🗒 ToDo popup active • ⚡ Mode • 📝 Prompt/Schema.",
                    "Save Tab Order": "In Settings → Tab Manager, Arrow mode lets you reorder tabs/panels. Click 'Save Tab Order' to persist both main tabs and per-tab panel order.",
                    "Show ToDo on Launch": "Enable the checkbox left of the ToDo header under Help & Guide to display ToDo on startup. ToDo v2 supports categories (Tasks, Bugs, Work-Orders, Notes, Completed) and priorities (High/Medium/Low) with color coding.",
                }
            },
            "Manual Guide": {
                "description": "Detailed, step-by-step usage for manual workflows and training.",
                "sub_tabs": {
                    "System Prompt & Tool Schema": "From Quick Actions → 📝 open the unified manager. Top toggles switch between System Prompt and Tool Schema. 'Select & Apply' remounts the model if mounted.",
                    "Temperature": "Click 🌡 to choose Manual (adjust slider in popup and Save) or Auto (uses training stats). Mode and value persist per session and are shown in the bottom indicator.",
                    "Think Time": "From Quick Actions → ⏱ set min/max seconds for the next input only. A ⏱ indicator appears while pending.",
                    "Chat Sessions": "Use 🆕 New Chat; 🗑 Delete Chat; ✏️ Rename Chat (Chat tab and Projects). History supports load/export/delete.",
                }
            },
            "Project Blueprint v2": {
                "description": "High-level system plan and current state.",
                "sub_tabs": {
                    "Overview": "See extras/blueprints/Trainer_Blue_Print_v2.0.txt for the v2 plan, roadmap, dependencies, and acceptance for v2.1.",
                }
            },
            "Git & Branching": {
                "description": "Local Git workflow and branches used for docs/blueprints.",
                "sub_tabs": {
                    "START_HERE": "Read START_HERE.md for setup, branching (docs/blueprint-v2), and commit conventions.",
                }
            },
            "Beginner’s Guide": {
                "description": "A step‑by‑step path from a fresh PyTorch model to a verified skillset: datasets → baseline → training → export → evaluation → compare.",
                "sub_tabs": {
                    "Getting Started": "Install or prepare a local PyTorch base model under Models/. In Models → Overview, select the base to work with. Ensure Ollama is running for inference (/api/chat).",
                    "Datasets": "Place evaluation suites under Training_Data‑Sets/Test (e.g., Tools/). Put training JSONL under Training_Data‑Sets (Tools, Coding, etc.). You can use or extend the examples provided.",
                    "Run Baseline": "Models → 🧪 Evaluation: choose a suite (e.g., Tools), select Tool Schema 'json_calls_full', and System Prompt 'Tools_JSON_Calls_Conformer'. Check 'Run as Baseline'. If no GGUF exists, export/pull first; the baseline will auto‑resume with the created tag and be saved under Models/benchmarks, set active.",
                    "Train & Level Up": "Training → Runner: commit your base and scripts, then train. Create Level 1 from adapters. Export level to GGUF (pick quant).",
                    "Evaluate & Compare": "Evaluate the Level; Compare vs the parent’s active baseline. Review overall Δ and per‑skill changes. History, Skills, and Baselines tabs update automatically.",
                    "Tips": "For Tools suite, json_calls_full + Tools_JSON_Calls_Conformer improves accuracy. Keep baselines full (no sampling). Use 'Create New' baselines to preserve history; optionally delete old when prompted."
                }
            },
            "Training Tab": {
                "description": "Prepare, run, and validate training. Left: sub‑tabs (Runner, Script Manager, Model Selection, Profiles, Summary). Right: selectors (Training Scripts, Prompts, Schemas).",
                "sub_tabs": {
                    "Runner": "Run training with a live console. Supports sequential execution (queues selected scripts) and delay between runs. Start/Stop/Clear/Status are fixed at the bottom for quick access. Early Stopping is shown only when a GPU is available. Save/Load Defaults persists runner controls.\n\nEvaluation Automation (scheduling): Auto‑run Baseline and Auto‑run Post‑Training.\nEvaluation Context: enable 'Use System Prompt' / 'Use Tool Schema' for automation.\nBaseline Controls: select baseline source (Auto/Base/Level) and open the Baselines manager.\n\n**(NEW)** Post-training evaluation is now automatically triggered after a training run, generating a report linked to the run's stats.",
                    "Script Manager": "A self-contained manager with three sub-tabs: 'Training Scripts', 'Prompts', and 'Schemas'. Each tab features an editor and a consistent set of action buttons at the bottom: `[➕ New File(s)] [📁 New Category] [💾 Save] [✏️ Rename] [🗑️ Delete] [❌ Clear] [📎 Copy]`. Selections in the main right-side panel of the Training Tab will load the corresponding file into the editor here.",
                    "Model Selection": "Dropdown lists only trainable models (local PyTorch and trained). Selecting shows detailed info (architecture, core parameters, latest training stats, and skills). Click 'Send To Training' to commit the selection (Runner's 'Training Model' updates then). Missing data is shown as 'Unverified'.",
                    "Profiles": "Save/load full setups: runner controls, committed model, right‑side selections (scripts/jsonl) and evaluation preferences (Use Prompt/Schema + selected names). Loading re‑applies toggles and selections.",
                    "Summary": "Read‑only preview: categories/files, core params, base model, and Use Prompt/Schema state (with names when enabled)."
                }
            },
            "Models Tab": {
                "description": "Inspect models, run evaluations, and compare results.",
                "sub_tabs": {
                    "Overview": "Parsed model info (type, path, size) and, when available, architecture/stats.",
                    "Raw Info": "Raw metadata (e.g., config.json) or Ollama show output.",
                    "Notes": "Free‑form notes per model.",
                    "Stats": "Training runs with filtering.\n\n**(NEW)** Now displays detailed evaluation results for each training run, including comparison against the active baseline (overall delta, regressions, improvements). Offers training suggestions if regressions are found.",
                    "Skills": "Skills aggregated from the latest evaluation report (per‑skill pass/total and status). **(NEW)** Now also displays the System Prompt and Tool Schema used for the evaluation.",
                    "🧪 Evaluation": "Suites come from `Training_Data-Sets/Test/<suite>`. Toggle 'Use System Prompt' / 'Use Tool Schema'. When a Tool Schema is selected, scoring is schema‑aware: tool name and args must validate against the schema before applying the test's policy (exact/partial/subset/function_call). 'Run as Pre‑Training Baseline' opens a confirm dialog and saves to `Models/benchmarks/`; otherwise to `Models/evaluations/`.",
                    "Baselines": "Manage baselines per model. View JSON, Set Active. Catalog stored at `Models/benchmarks/index.json`. Active baseline is used for regression checks and quick comparisons.",
                    "Compare": "Parent‑centric compare with three modes: (1) Baseline vs Baseline (Parent), (2) Latest Eval vs Reference (Parent), and (3) Advanced: Other Model (latest eval). Baseline lists autoload for the selected Parent with readable labels (date | pass% | suite | schema | prompt). Buttons below the result: '🧠 Generate Training Suggestions' (reason breakdown + JSONL stubs) and '💾 Save Example Stubs' (writes to Training_Data‑Sets/Tools).",
                    "Model List Sidebar": "Groups into Base (PyTorch), Trained, and Ollama (inference‑only)."
                }
            },
            "Settings Tab": {
                "description": "Global preferences and developer tools.",
                "sub_tabs": {
                    "General": "Overview and quick actions (save/reset settings).",
                    "Paths": "Key directories used by the app.",
                    "Training Defaults": "Default epochs/batch/lr used by Runner when not overridden.",
                    "Interface": "Tab visibility/order and reordering mode (static/dnd).",
                    "Tab Manager": "Create/edit tabs and panels programmatically.",
                    "Resources": "CPU threads, RAM %, seq length, gradient accumulation (applied in training).",
                    "Debug": "Live log viewer with history and 'Copy to Clipboard'. Captures wrapper early logs.",
                    "Evaluation Policy": "Regression checks: enable, drop threshold (in %), strict notifications; auto‑rollback is reserved for future use."
                }
            }
        }

        for main_tab_name, main_tab_data in self.help_structure.items():
            tab_node = self.help_tree.insert(
                '', 'end', text=main_tab_name, open=True, tags=('main_tab',)
            )
            # Add description for main tab
            if "description" in main_tab_data:
                self.help_tree.insert(tab_node, 'end', text="Description", tags=('description',))

            for sub_tab_name in main_tab_data.get("sub_tabs", {}).keys():
                self.help_tree.insert(tab_node, 'end', text=sub_tab_name)

    def on_help_topic_select(self, event):
        """Displays the help text for the selected topic."""
        selection = self.help_tree.selection()
        if not selection:
            return

        item_id = selection[0]
        parent_id = self.help_tree.parent(item_id)
        
        help_text = "No help available for this topic."

        if parent_id: # It's a sub-tab or a description node
            main_tab_text = self.help_tree.item(parent_id, 'text')
            item_text = self.help_tree.item(item_id, 'text')
            
            if item_text == "Description":
                help_text = self.help_structure.get(main_tab_text, {}).get("description", help_text)
            else:
                help_text = self.help_structure.get(main_tab_text, {}).get("sub_tabs", {}).get(item_text, help_text)
        else: # It's a main tab
            main_tab_text = self.help_tree.item(item_id, 'text')
            help_text = self.help_structure.get(main_tab_text, {}).get("description", help_text)

        # Ensure help text pane is visible (add to paned if not already present)
        try:
            panes = [str(p) for p in getattr(self.help_paned, 'panes')()] if hasattr(self, 'help_paned') else []
            if hasattr(self, 'help_text_frame') and str(self.help_text_frame) not in panes:
                self.help_paned.insert(1, self.help_text_frame, weight=1)
        except Exception:
            pass

        self.help_display.config(state=tk.NORMAL)
        self.help_display.delete(1.0, tk.END)
        self.help_display.insert(tk.END, help_text)
        self.help_display.config(state=tk.DISABLED)

    def create_general_settings(self, parent):
        """Create general settings section using the proven scrollable layout pattern."""
        # This pattern (Canvas + Scrollbar + pack) is known to work from other tabs.
        canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        content_frame = ttk.Frame(canvas, style='Category.TFrame')

        content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
        
        content_frame.columnconfigure(0, weight=1) # Allow sections to expand horizontally

        # --- Content goes into content_frame using grid ---
        current_row = 0

        # Application info
        info_section = ttk.LabelFrame(content_frame, text="ℹ️ Application Info", style='TLabelframe')
        info_section.grid(row=current_row, column=0, sticky='ew', padx=10, pady=10); current_row += 1
        info_section.columnconfigure(1, weight=1)
        ttk.Label(info_section, text="Application:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info_section, text="OpenCode Trainer", style='Config.TLabel').grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info_section, text="Version:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info_section, text="1.3 (Debug Enhanced)", style='Config.TLabel').grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info_section, text="Location:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info_section, text=str(TRAINER_ROOT), style='Config.TLabel', wraplength=400, justify=tk.LEFT).grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)

        # Quick actions
        actions_section = ttk.LabelFrame(content_frame, text="⚡ Quick Actions", style='TLabelframe')
        actions_section.grid(row=current_row, column=0, sticky='ew', padx=10, pady=10); current_row += 1
        actions_section.columnconfigure(0, weight=1)
        ttk.Button(actions_section, text="🔄 Refresh Ollama Models", command=self.refresh_models, style='Select.TButton').grid(row=0, column=0, sticky=tk.EW, padx=10, pady=5)
        ttk.Button(actions_section, text="🗑️ Clear Training Cache", command=self.clear_cache, style='Select.TButton').grid(row=1, column=0, sticky=tk.EW, padx=10, pady=5)
        ttk.Button(actions_section, text="📊 View System Info", command=self.show_system_info, style='Select.TButton').grid(row=2, column=0, sticky=tk.EW, padx=10, pady=5)

        # Main Action Buttons
        button_frame = ttk.Frame(content_frame, style='Category.TFrame')
        button_frame.grid(row=current_row, column=0, sticky='ew', padx=10, pady=(20, 10)); current_row += 1
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        ttk.Button(button_frame, text="💾 Save All Settings", command=self.save_settings_to_file, style='Action.TButton').grid(row=0, column=0, padx=(0, 5), sticky=tk.EW)
        ttk.Button(button_frame, text="⚠️ Reset All Settings", command=self.reset_all_settings_to_default, style='Select.TButton').grid(row=0, column=1, padx=(5, 0), sticky=tk.EW)

    def reset_all_settings_to_default(self):
        """Resets all settings in this tab to their hardcoded default values."""
        if not messagebox.askyesno("Confirm Reset", "Are you sure you want to reset ALL settings to their original defaults?\nThis cannot be undone."):
            return

        log_message("SETTINGS: User initiated reset of all settings to default.")

        try:
            # Reset Training Defaults
            if hasattr(self, 'default_epochs'): self.default_epochs.set(3)
            if hasattr(self, 'default_batch'): self.default_batch.set(2)
            if hasattr(self, 'default_lr'): self.default_lr.set("2e-4")

            # Reset Interface
            if hasattr(self, 'auto_refresh'): self.auto_refresh.set(True)
            if hasattr(self, 'show_debug'): self.show_debug.set(False)
            if hasattr(self, 'confirm_training'): self.confirm_training.set(True)

            # Reset Resources
            if hasattr(self, 'max_cpu_threads'): self.max_cpu_threads.set(2)
            if hasattr(self, 'max_ram_percent'): self.max_ram_percent.set(70)
            if hasattr(self, 'max_seq_length'): self.max_seq_length.set(256)
            if hasattr(self, 'gradient_accumulation'): self.gradient_accumulation.set(16)

            log_message("SETTINGS: All settings variables have been reset in the UI.")
            messagebox.showinfo("Reset Complete", "All settings have been reset to their defaults. Click 'Save All Settings' to make them permanent.")
        except Exception as e:
            log_message(f"SETTINGS ERROR: Failed to reset settings. Error: {e}")
            messagebox.showerror("Reset Failed", f"An error occurred while resetting settings: {e}")

    def refresh_models(self):
        """Refresh Ollama models list"""
        messagebox.showinfo("Refresh Models", "Models list will be refreshed on next restart.")

    def clear_cache(self):
        """Clear training cache files"""
        if messagebox.askyesno("Clear Cache", "Clear all temporary training files?"):
            try:
                temp_files = list(DATA_DIR.glob("temp_*.jsonl"))
                for f in temp_files:
                    f.unlink()
                messagebox.showinfo("Cache Cleared", f"Removed {len(temp_files)} temporary files.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear cache: {e}")

    def show_system_info(self):
        """Show system information"""
        import platform
        info = f"""System Information:

OS: {platform.system()} {platform.release()}
Python: {platform.python_version()}
Machine: {platform.machine()}

Trainer Root: {TRAINER_ROOT}
Models Dir: {MODELS_DIR}
Data Dir: {DATA_DIR}
"""
        messagebox.showinfo("System Info", info)

    def create_path_settings(self, parent):
        """Create path configuration section"""
        section = ttk.LabelFrame(parent, text="📁 Paths", style='TLabelframe')
        section.pack(fill=tk.X, pady=10)

        # Models directory
        ttk.Label(section, text="Models Directory:", style='Config.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        models_path = ttk.Label(section, text=str(MODELS_DIR), style='Config.TLabel')
        models_path.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        # Training data directory
        ttk.Label(section, text="Training Data:", style='Config.TLabel').grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=5
        )
        data_path = ttk.Label(section, text=str(TRAINING_DATA_DIR),
                              style='Config.TLabel')
        data_path.grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)

    def create_training_defaults(self, parent):
        """Create default training parameters section"""
        section = ttk.LabelFrame(parent, text="🎯 Training Defaults", style='TLabelframe')
        section.pack(fill=tk.X, pady=10)

        # Default epochs
        ttk.Label(section, text="Default Training Runs:", style='Config.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.default_epochs = tk.IntVar(value=self.settings.get('default_epochs', 3))
        epochs_spin = ttk.Spinbox(
            section,
            from_=1,
            to=100,
            textvariable=self.default_epochs,
            width=10
        )
        epochs_spin.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        # Default batch size
        ttk.Label(section, text="Default Batch Size:", style='Config.TLabel').grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.default_batch = tk.IntVar(value=self.settings.get('default_batch', 2))
        batch_spin = ttk.Spinbox(
            section,
            from_=1,
            to=32,
            textvariable=self.default_batch,
            width=10
        )
        batch_spin.grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)

        # Default learning rate
        ttk.Label(section, text="Default Learning Strength:", style='Config.TLabel').grid(
            row=2, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.default_lr = tk.StringVar(value=self.settings.get('default_learning_rate', '2e-4'))
        lr_entry = ttk.Entry(section, textvariable=self.default_lr, width=15)
        lr_entry.grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)

    def create_ui_settings(self, parent):
        """Create UI preferences section"""
        section = ttk.LabelFrame(parent, text="🎨 Interface", style='TLabelframe')
        section.pack(fill=tk.X, pady=10)

        # Auto-refresh models list
        self.auto_refresh = tk.BooleanVar(value=self.settings.get('auto_refresh_models', True))
        ttk.Checkbutton(
            section,
            text="Auto-refresh models list on startup",
            variable=self.auto_refresh,
            style='Category.TCheckbutton'
        ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)

        # Show debug info
        self.show_debug = tk.BooleanVar(value=self.settings.get('show_debug', False))
        ttk.Checkbutton(
            section,
            text="Show debug information",
            variable=self.show_debug,
            style='Category.TCheckbutton'
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)

        # Confirm before training
        self.confirm_training = tk.BooleanVar(value=self.settings.get('confirm_training', True))
        ttk.Checkbutton(
            section,
            text="Confirm before starting training",
            variable=self.confirm_training,
            style='Category.TCheckbutton'
        ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)

    def create_tab_manager(self, parent):
        """Create tab manager interface for creating/managing custom tabs"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # Scrollable root for entire Tab Manager panel
        scroll_root = ttk.Frame(parent)
        scroll_root.grid(row=0, column=0, sticky=tk.NSEW)
        scroll_root.columnconfigure(0, weight=1)
        scroll_root.rowconfigure(0, weight=1)

        canvas = tk.Canvas(scroll_root, borderwidth=0, highlightthickness=0)
        vscroll = ttk.Scrollbar(scroll_root, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.grid(row=0, column=0, sticky=tk.NSEW)
        vscroll.grid(row=0, column=1, sticky=tk.NS)

        # Inner container that actually holds the content
        container = ttk.Frame(canvas)
        # Create window for inner frame
        canvas_window = canvas.create_window((0, 0), window=container, anchor="nw")

        # Configure resizing behavior
        def _on_container_configure(event=None):
            try:
                canvas.configure(scrollregion=canvas.bbox("all"))
                # Keep inner frame width synced to canvas width for nice layout
                canvas.itemconfigure(canvas_window, width=canvas.winfo_width())
            except Exception:
                pass

        container.bind("<Configure>", _on_container_configure)
        canvas.bind("<Configure>", _on_container_configure)

        # Mouse wheel on hover for the canvas area (bind_all only while hovering)
        try:
            self._bind_mousewheel_to_canvas_hover(canvas, hover_widgets=[canvas, container])
        except Exception:
            pass

        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        # Title
        ttk.Label(
            container,
            text="🗂️ Tab Manager - Create Custom Tabs",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).grid(row=0, column=0, pady=10, sticky=tk.W)

        # Create Tab Section
        create_frame = ttk.LabelFrame(container, text="➕ Create New Tab", style='TLabelframe')
        create_frame.grid(row=1, column=0, sticky=tk.EW, pady=10)

        # Tab name input
        name_frame = ttk.Frame(create_frame)
        name_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(name_frame, text="Tab Name:", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 10))
        self.new_tab_name = tk.StringVar()
        ttk.Entry(
            name_frame,
            textvariable=self.new_tab_name,
            font=("Arial", 10),
            width=30
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Number of sub-tabs
        subtabs_frame = ttk.Frame(create_frame)
        subtabs_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(subtabs_frame, text="Sub-tabs:", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 10))
        self.num_subtabs = tk.IntVar(value=3)
        ttk.Spinbox(
            subtabs_frame,
            from_=1,
            to=10,
            textvariable=self.num_subtabs,
            width=10
        ).pack(side=tk.LEFT)

        # Side menu option
        options_frame = ttk.Frame(create_frame)
        options_frame.pack(fill=tk.X, padx=10, pady=10)

        self.has_side_menu = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="Include side menu (like Model/Settings tabs)",
            variable=self.has_side_menu,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W)

        # Create button
        ttk.Button(
            create_frame,
            text="🚀 Create Tab",
            command=self.create_new_tab,
            style='Action.TButton'
        ).pack(pady=10, padx=10, fill=tk.X)

        # Tab Visibility Section
        visibility_frame = ttk.LabelFrame(container, text="👁️ Tab Visibility", style='TLabelframe')
        visibility_frame.grid(row=2, column=0, sticky=tk.EW, pady=10)
        visibility_frame.columnconfigure(0, weight=1)

        # Populate with checkboxes for each tab
        self._populate_tab_visibility_controls(visibility_frame)

        # Existing Tabs Browser Section
        browser_frame = ttk.LabelFrame(container, text="📂 Tab Browser & Editor", style='TLabelframe')
        browser_frame.grid(row=3, column=0, sticky=tk.NSEW, pady=10) # Adjusted row
        browser_frame.columnconfigure(0, weight=1)
        browser_frame.rowconfigure(0, weight=1)

        # Split into left (tree) and right (editor)
        browser_paned = ttk.PanedWindow(browser_frame, orient=tk.HORIZONTAL)
        browser_paned.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)

        # Left: Tree view of tabs/panels
        tree_frame = ttk.Frame(browser_paned)
        browser_paned.add(tree_frame, weight=1)

        ttk.Label(
            tree_frame,
            text="Tabs & Panels",
            font=("Arial", 10, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(pady=5)

        # Tree view with scrollbar
        tree_container = ttk.Frame(tree_frame)
        tree_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        tree_scroll = ttk.Scrollbar(tree_container, orient="vertical")
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tabs_tree = ttk.Treeview(
            tree_container,
            yscrollcommand=tree_scroll.set,
            selectmode='browse',
            height=12
        )
        self.tabs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.tabs_tree.yview)

        # Mouse wheel on hover for the structure tree (bind to both tree and its container)
        try:
            self._bind_mousewheel_to_tree(self.tabs_tree, tree_container)
        except Exception:
            pass

        # Configure tree columns
        self.tabs_tree.heading('#0', text='Structure')

        # Style the treeview for better visibility
        style = ttk.Style()
        tree_style = "TabManager.Treeview"
        style.configure(
            tree_style,
            background="#2b2b2b",
            foreground="white",
            fieldbackground="#2b2b2b",
            borderwidth=0
        )
        style.map(
            tree_style,
            background=[('selected', '#3d3d3d')],
            foreground=[('selected', '#61dafb')]
        )
        try:
            self.tabs_tree.configure(style=tree_style)
        except tk.TclError:
            pass

        # Configure tree tags for different item types
        self.tabs_tree.tag_configure('tab', foreground='#61dafb', font=('Arial', 10, 'bold'))
        self.tabs_tree.tag_configure('file', foreground='#ffffff')
        self.tabs_tree.tag_configure('panel', foreground='#a8dadc')

        self.tabs_tree.bind('<<TreeviewSelect>>', self.on_tree_select)

        # Right: Panel editor/actions
        editor_frame = ttk.Frame(browser_paned)
        browser_paned.add(editor_frame, weight=2)

        ttk.Label(
            editor_frame,
            text="Panel Editor",
            font=("Arial", 10, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(pady=5)

        # Selected item info
        self.selected_info_label = ttk.Label(
            editor_frame,
            text="Select a tab or panel from the tree",
            style='Config.TLabel'
        )
        self.selected_info_label.pack(pady=10)

        # Panel selector UI (appears when a tab is selected)
        self.panel_select_container = ttk.Frame(editor_frame)
        ttk.Label(self.panel_select_container, text="Select Panel:", style='Config.TLabel').pack(side=tk.LEFT, padx=(0,8))
        self.panel_selector = ttk.Combobox(self.panel_select_container, state='readonly', width=28)
        self.panel_selector.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.panel_selector.bind('<<ComboboxSelected>>', self._on_panel_combo_changed)
        # Initially hidden
        self.panel_select_container.pack_forget()
        # Panel selection indicator
        self.panel_selected_label = ttk.Label(editor_frame, text="", style='Config.TLabel')
        self.panel_selected_label.pack(pady=(4,10))
        # Track which tab drives the panel selector
        self.current_tab_for_panel_selector = None

        # Action buttons
        actions_frame = ttk.Frame(editor_frame)
        actions_frame.pack(fill=tk.X, padx=10, pady=10)

        self.move_left_button = ttk.Button(
            actions_frame,
            text="⬅️ Move Left",
            command=lambda: self.move_tab("left"),
            style='Action.TButton'
        )
        
        self.move_right_button = ttk.Button(
            actions_frame,
            text="➡️ Move Right",
            command=lambda: self.move_tab("right"),
            style='Action.TButton'
        )

        ttk.Button(
            actions_frame,
            text="➕ Add Panel",
            command=self.add_new_panel,
            style='Action.TButton'
        ).pack(fill=tk.X, pady=2)

        ttk.Button(
            actions_frame,
            text="✏️ Edit Panel",
            command=self.edit_selected_panel,
            style='Select.TButton'
        ).pack(fill=tk.X, pady=2)

        ttk.Button(
            actions_frame,
            text="🗑️ Delete Panel",
            command=self.delete_selected_panel,
            style='Select.TButton'
        ).pack(fill=tk.X, pady=2)

        ttk.Button(
            actions_frame,
            text="🔄 Refresh",
            command=self.refresh_tabs_tree,
            style='Select.TButton'
        ).pack(fill=tk.X, pady=2)

        # Populate tree
        self.refresh_tabs_tree()

        # Store selected item
        self.selected_tree_item = None

        # Initially hide the move buttons
        self.move_left_button.pack_forget()
        self.move_right_button.pack_forget()

    def _bind_mousewheel_to_tree(self, tree_widget, container_widget=None):
        """Enable mouse wheel scrolling on hover for Treeview (Linux/Windows/Mac)."""
        import platform
        system = platform.system()

        targets = [tree_widget]
        if container_widget is not None:
            targets.append(container_widget)

        if system == "Linux":
            def _on_up(event):
                tree_widget.yview_scroll(-1, "units")
                return "break"
            def _on_down(event):
                tree_widget.yview_scroll(1, "units")
                return "break"
            for w in targets:
                w.bind("<Button-4>", _on_up, add=True)
                w.bind("<Button-5>", _on_down, add=True)
        else:
            def _on_wheel(event):
                try:
                    delta = int(-1 * (event.delta / 120))
                except Exception:
                    delta = -1
                tree_widget.yview_scroll(delta, "units")
                return "break"
            for w in targets:
                w.bind("<MouseWheel>", _on_wheel, add=True)

    def _bind_mousewheel_to_canvas_hover(self, canvas_widget, hover_widgets=None):
        """Enable scrolling the Tab Manager canvas with the mouse wheel while hovering.

        Uses bind_all only during hover to capture wheel events anywhere over the
        scrollable area (including inner child widgets), but allows inner widgets
        like the Treeview to consume events by returning "break" first.
        """
        import platform
        system = platform.system()

        if hover_widgets is None:
            hover_widgets = [canvas_widget]

        # Handlers that scroll the canvas
        if system == "Linux":
            def _wheel_up(event):
                canvas_widget.yview_scroll(-1, "units")
                return "break"
            def _wheel_down(event):
                canvas_widget.yview_scroll(1, "units")
                return "break"
            def _enable(_e=None):
                canvas_widget.bind_all("<Button-4>", _wheel_up)
                canvas_widget.bind_all("<Button-5>", _wheel_down)
            def _disable(_e=None):
                canvas_widget.unbind_all("<Button-4>")
                canvas_widget.unbind_all("<Button-5>")
        else:
            def _wheel_any(event):
                try:
                    delta = int(-1 * (event.delta / 120))
                except Exception:
                    delta = -1
                canvas_widget.yview_scroll(delta, "units")
                return "break"
            def _enable(_e=None):
                canvas_widget.bind_all("<MouseWheel>", _wheel_any)
            def _disable(_e=None):
                canvas_widget.unbind_all("<MouseWheel>")

        # Attach enter/leave to both the canvas and inner container
        for w in hover_widgets:
            w.bind("<Enter>", _enable, add=True)
            w.bind("<Leave>", _disable, add=True)

    def create_new_tab(self):
        """Create a new tab with user specifications"""
        from tab_generator import TabGenerator

        tab_name = self.new_tab_name.get().strip()
        if not tab_name:
            messagebox.showwarning("No Name", "Please enter a tab name.")
            return

        generator = TabGenerator(DATA_DIR)
        result = generator.create_tab(
            tab_name=tab_name,
            num_subtabs=self.num_subtabs.get(),
            has_side_menu=self.has_side_menu.get()
        )

        if result['success']:
            messagebox.showinfo(
                "Tab Created",
                f"✅ Tab '{tab_name}' created successfully!\n\n"
                f"Files created:\n" + '\n'.join([f"  • {Path(f).name}" for f in result['files']]) +
                f"\n\nRestart the application to see the new tab."
            )
            self.new_tab_name.set("")
            self.refresh_tabs_tree()
        else:
            messagebox.showerror("Creation Failed", result['error'])

    def refresh_tabs_tree(self):
        """Refresh the tree view of tabs and panels - includes ALL tabs"""
        log_message("SETTINGS: Refreshing tabs tree.")
        log_message(f"SETTINGS: Tab order from settings: {self.settings.get('tab_order')}")
        # Clear existing tree
        for item in self.tabs_tree.get_children():
            self.tabs_tree.delete(item)
        # Reset panel file mapping
        self.panel_file_map = {}

        tabs_dir = None
        for candidate in (
            TRAINER_ROOT / "Data" / "tabs",  # source code location
            DATA_DIR / "tabs"               # version-scoped copy if present
        ):
            if candidate.exists():
                tabs_dir = candidate
                break

        if tabs_dir is None:
            return

        # Define built-in tabs with special handling
        built_in_tabs = {
            'settings_tab': {
                'display': 'Settings',
                'icon': '⚙️',
                'main_file': 'settings_tab.py',
                'panels': []
            },
            'training_tab': {
                'display': 'Training',
                'icon': '⚙️',
                'main_file': 'training_tab.py',
                'panels': [
                    'runner_panel.py',
                    'category_manager_panel.py',
                    'dataset_panel.py',
                    'config_panel.py',
                    'profiles_panel.py',
                    'summary_panel.py'
                ]
            },
            'models_tab': {
                'display': 'Models',
                'icon': '🧠',
                'main_file': 'models_tab.py',
                'panels': []
            }
        }

        # Get the saved tab order
        saved_order = self.settings.get('tab_order', ['training_tab', 'models_tab', 'custom_code_tab', 'settings_tab'])
        
        # Get all tab directories
        all_tab_dirs = {tab_dir.name: tab_dir for tab_dir in sorted(tabs_dir.iterdir()) if tab_dir.is_dir() and not tab_dir.name.startswith('__')}
        
        processed_tabs = set()

        # Add tabs in the saved order
        for tab_dir_name in saved_order:
            if tab_dir_name in all_tab_dirs:
                self._add_tab_to_tree(all_tab_dirs[tab_dir_name], built_in_tabs)
                processed_tabs.add(tab_dir_name)

        # Add any remaining tabs that were not in the saved order
        for tab_dir_name, tab_dir in all_tab_dirs.items():
            if tab_dir_name not in processed_tabs:
                self._add_tab_to_tree(tab_dir, built_in_tabs)

    def _add_tab_to_tree(self, tab_dir, built_in_tabs):
        """Add a single tab node and its live panel headers, hiding raw files."""
        tab_name = tab_dir.name

        # Determine display name and icon
        if tab_name in built_in_tabs:
            tab_info = built_in_tabs[tab_name]
            tab_display_name = tab_info['display']
            icon = tab_info['icon']
        else:
            tab_display_name = tab_dir.name.replace('_tab', '').replace('_', ' ').title()
            icon = '📂'

        # Add tab as root node (store tab_name, not path)
        tab_node = self.tabs_tree.insert(
            '', 'end',
            text=f"{icon} {tab_display_name}",
            values=(tab_name, 'tab'),
            tags=('tab',)
        )

        # Add panel headers from the live notebook (if available)
        instance = None
        try:
            if self.tab_instances and tab_name in self.tab_instances:
                instance = self.tab_instances[tab_name]['instance']
        except Exception:
            instance = None

        notebook = None
        if instance is not None:
            # Known notebook attributes by tab
            for attr in (
                'training_notebook',    # TrainingTab
                'sub_notebook',         # CustomCodeTab
                'settings_notebook',    # SettingsTab
                'model_info_notebook',  # ModelsTab
                'models_notebook'       # Fallback (older naming)
            ):
                nb = getattr(instance, attr, None)
                if nb is not None:
                    notebook = nb
                    break

        if notebook is not None:
            try:
                tab_ids = notebook.tabs()
                for i, tid in enumerate(tab_ids):
                    try:
                        header = notebook.tab(tid, 'text')
                    except Exception:
                        header = f"Panel {i+1}"

                    # Record potential file mapping for known tabs
                    file_path = self._resolve_panel_file(tab_name, header, tab_dir)
                    if file_path:
                        self.panel_file_map[(tab_name, header)] = file_path

                    self.tabs_tree.insert(
                        tab_node,
                        'end',
                        text=f"🔧 {header}",
                        values=(f"{tab_name}|{header}", 'panel_header'),
                        tags=('panel',)
                    )
            except Exception:
                pass

        # Expand by default
        self.tabs_tree.item(tab_node, open=True)

    def _resolve_panel_file(self, tab_name, header_text, tab_dir):
        """Best-effort mapping from panel header to its source file for built-in tabs."""
        try:
            if tab_name == 'training_tab':
                mapping = {
                    'Runner': 'runner_panel.py',
                    'Script Manager': 'category_manager_panel.py',
                    'Model Selection': 'model_selection_panel.py',
                    'Profiles': 'profiles_panel.py',
                    'Summary': 'summary_panel.py',
                }
                fn = mapping.get(header_text)
                if fn:
                    p = tab_dir / fn
                    return p if p.exists() else None
            # Custom Code panels are all in custom_code_tab.py; skip mapping to file
        except Exception:
            pass
        return None

    def on_tree_select(self, event):
        """Handle tree item selection"""
        selection = self.tabs_tree.selection()
        if not selection:
            if hasattr(self, 'move_left_button'):
                self.move_left_button.config(state=tk.DISABLED)
                self.move_right_button.config(state=tk.DISABLED)
            # Hide panel selector
            self.panel_select_container.pack_forget()
            self.panel_selected_label.config(text="")
            return

        item = selection[0]
        values = self.tabs_tree.item(item, 'values')

        if not values:
            if hasattr(self, 'move_left_button'):
                self.move_left_button.config(state=tk.DISABLED)
                self.move_right_button.config(state=tk.DISABLED)
            return

        raw_key, item_type = values
        # Decode selection meta
        if item_type == 'tab':
            tab_name = raw_key
            self.selected_tree_item = {'type': 'tab', 'tab_name': tab_name, 'path': Path(DATA_DIR) / 'tabs' / tab_name}
        elif item_type == 'panel_header':
            # raw_key = "tab_name|header"
            try:
                tab_name, header = raw_key.split('|', 1)
            except ValueError:
                tab_name, header = raw_key, ''
            info = {'type': 'panel_header', 'tab_name': tab_name, 'panel_header': header}
            file_path = self.panel_file_map.get((tab_name, header))
            if file_path:
                info['path'] = file_path
            self.selected_tree_item = info
        else:
            # Fallback to previous behavior
            self.selected_tree_item = {'path': Path(raw_key), 'type': item_type}

        # Update info label and button states
        if item_type in ('tab', 'panel_header') and self.reorder_mode.get() == 'arrow':
            # Always persist Tab label at the top
            tab_name_for_label = self.selected_tree_item.get('tab_name') if item_type == 'panel_header' else self.selected_tree_item.get('tab_name')
            self.selected_info_label.config(text=f"Tab: {tab_name_for_label}")
            if hasattr(self, 'move_left_button'):
                self.move_left_button.config(state=tk.NORMAL)
                self.move_right_button.config(state=tk.NORMAL)
            # Show and sync panel selector
            if item_type == 'tab':
                self._show_panel_selector(self.selected_tree_item.get('tab_name'))
            else:
                header = self.selected_tree_item.get('panel_header')
                self._show_panel_selector(self.selected_tree_item.get('tab_name'), preselect=header)
                # Show panel indicator separately
                self.panel_selected_label.config(text=f"Panel: {header}")
        else:
            if hasattr(self, 'move_left_button'):
                self.move_left_button.config(state=tk.DISABLED)
                self.move_right_button.config(state=tk.DISABLED)
            if item_type == 'tab':
                self.selected_info_label.config(text=f"Tab: {self.selected_tree_item.get('tab_name')}")
                self._show_panel_selector(self.selected_tree_item.get('tab_name'))
            elif item_type == 'panel_header':
                # Persist Tab label and show panel indicator below
                self.selected_info_label.config(text=f"Tab: {self.selected_tree_item.get('tab_name')}")
                header = self.selected_tree_item.get('panel_header')
                self._show_panel_selector(self.selected_tree_item.get('tab_name'), preselect=header)
                self.panel_selected_label.config(text=f"Panel: {header}")

    def _get_tab_notebook(self, tab_name):
        """Return the ttk.Notebook for the given tab instance, if any."""
        try:
            if not self.tab_instances or tab_name not in self.tab_instances:
                return None
            instance = self.tab_instances[tab_name]['instance']
            for attr in (
                'training_notebook',
                'sub_notebook',
                'settings_notebook',
                'model_info_notebook',
                'models_notebook'
            ):
                nb = getattr(instance, attr, None)
                if nb is not None:
                    return nb
        except Exception:
            return None
        return None

    def _get_panel_headers(self, tab_name):
        """List of panel header texts for the tab's notebook."""
        nb = self._get_tab_notebook(tab_name)
        if nb is None:
            return []
        headers = []
        try:
            for tid in nb.tabs():
                try:
                    headers.append(nb.tab(tid, 'text'))
                except Exception:
                    headers.append('')
        except Exception:
            pass
        return headers

    def _show_panel_selector(self, tab_name, preselect=None):
        """Populate and show the panel selector for a given tab."""
        headers = [h for h in self._get_panel_headers(tab_name) if h]
        if not headers:
            self.panel_select_container.pack_forget()
            self.panel_selected_label.config(text="")
            self.current_tab_for_panel_selector = None
            return
        self.current_tab_for_panel_selector = tab_name
        # Update combobox values and selection
        try:
            self.panel_selector['values'] = headers
        except Exception:
            pass
        if preselect and preselect in headers:
            self.panel_selector.set(preselect)
            self.panel_selected_label.config(text=f"Panel: {preselect}")
        else:
            # No preselect: leave empty until user picks
            try:
                self.panel_selector.set("")
            except Exception:
                pass
            self.panel_selected_label.config(text="")
        # Show container
        self.panel_select_container.pack(fill=tk.X, padx=10)

        # Do not change selected_tree_item here unless preselect used
        if preselect and preselect in headers:
            selected_header = preselect
            info = {'type': 'panel_header', 'tab_name': tab_name, 'panel_header': selected_header}
            file_path = self.panel_file_map.get((tab_name, selected_header))
            if file_path:
                info['path'] = file_path
            self.selected_tree_item = info

    def _on_panel_combo_changed(self, event=None):
        """Handle selection change from the panel combobox."""
        tab_name = self.current_tab_for_panel_selector
        if not tab_name:
            return
        header = self.panel_selector.get()
        self.panel_selected_label.config(text=f"Panel: {header}")
        info = {'type': 'panel_header', 'tab_name': tab_name, 'panel_header': header}
        file_path = self.panel_file_map.get((tab_name, header))
        if file_path:
            info['path'] = file_path
        self.selected_tree_item = info

    def add_new_panel(self):
        """Add a new panel to selected tab"""
        if not self.selected_tree_item or self.selected_tree_item['type'] != 'tab':
            messagebox.showwarning(
                "No Tab Selected",
                "Please select a tab from the tree to add a panel."
            )
            return

        from tkinter import simpledialog
        panel_name = simpledialog.askstring(
            "New Panel",
            "Enter panel name (e.g., 'analytics', 'settings'):"
        )

        if not panel_name:
            return

        # Sanitize panel name
        import re
        panel_name = re.sub(r'[^a-zA-Z0-9_]', '_', panel_name).lower()

        tab_dir = self.selected_tree_item['path']
        panel_file = tab_dir / f"{panel_name}.py"

        if panel_file.exists():
            messagebox.showerror("Error", f"Panel '{panel_name}.py' already exists!")
            return

        # Generate panel content
        class_name = ''.join(word.capitalize() for word in panel_name.split('_'))
        panel_content = f'''"""
{class_name} Panel
"""

import tkinter as tk
from tkinter import ttk


class {class_name}:
    """Panel for {panel_name}"""

    def __init__(self, parent, style):
        self.parent = parent
        self.style = style

    def create_ui(self):
        """Create the panel UI"""
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)

        # Main container
        container = ttk.Frame(self.parent, style='Category.TFrame')
        container.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)

        # Title
        ttk.Label(
            container,
            text="{class_name} Panel",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(pady=10)

        # Content
        ttk.Label(
            container,
            text="Add your content here",
            style='Config.TLabel'
        ).pack(pady=20)
'''

        try:
            panel_file.write_text(panel_content)
            messagebox.showinfo(
                "Panel Created",
                f"✅ Panel '{panel_name}.py' created!\n\n"
                f"Remember to:\n"
                f"1. Import it in the main tab file\n"
                f"2. Add it to the notebook\n"
                f"3. Restart the application"
            )
            self.refresh_tabs_tree()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create panel: {e}")

    def edit_selected_panel(self):
        """Open selected panel file in default editor (when resolvable)."""
        if not self.selected_tree_item:
            messagebox.showwarning(
                "No Selection",
                "Please select a file from the tree to edit.\n\n"
                "You can edit:\n"
                "• Panel files (🔧)\n"
                "• Main tab files (📄)"
            )
            return

        stype = self.selected_tree_item.get('type')
        if stype not in ['panel', 'main_file', 'panel_header']:
            messagebox.showwarning(
                "Invalid Selection",
                f"Cannot edit {stype}.\n\n"
                "Please select a panel file (🔧) or main file (📄)."
            )
            return

        # For panel_header, we may not have a file path
        file_path = self.selected_tree_item.get('path')
        if stype == 'panel_header' and not file_path:
            messagebox.showinfo(
                "Not Editable",
                "This panel does not map to a single source file."
            )
            return

        if not file_path.exists():
            messagebox.showerror(
                "File Not Found",
                f"File does not exist:\n{file_path}"
            )
            return

        try:
            import subprocess
            subprocess.Popen(['xdg-open', str(file_path)])
            messagebox.showinfo(
                "Opening File",
                f"Opening in default editor:\n\n{file_path.name}\n\n"
                "The file should open shortly in your system's default Python editor."
            )
        except Exception as e:
            messagebox.showerror("Failed to Open", f"Failed to open file: {e}")

    def delete_selected_panel(self):
        """Delete selected panel file with strict confirmation"""
        if not self.selected_tree_item:
            messagebox.showwarning(
                "No Selection",
                "Please select a panel file from the tree to delete."
            )
            return

        if self.selected_tree_item['type'] != 'panel':
            messagebox.showwarning(
                "Invalid Selection",
                "You can only delete panel files.\n\n"
                f"Selected: {self.selected_tree_item['type']}\n\n"
                "Please select a panel file (🔧 icon)."
            )
            return

        file_path = self.selected_tree_item['path']
        file_name = file_path.name

        # Check if it's a built-in critical panel
        critical_panels = [
            'runner_panel.py', 'category_manager_panel.py',
            'dataset_panel.py', 'config_panel.py',
            'profiles_panel.py', 'summary_panel.py'
        ]

        if file_name in critical_panels:
            messagebox.showerror(
                "Cannot Delete Built-in Panel",
                f"'{file_name}' is a built-in panel and cannot be deleted.\n\n"
                "This panel is essential to the application's functionality."
            )
            return

        # First confirmation
        if not messagebox.askyesno(
            "⚠️ Confirm Delete - Step 1/2",
            f"Are you sure you want to delete:\n\n"
            f"    {file_name}\n\n"
            f"This action CANNOT be undone!"
        ):
            return

        # Second strict confirmation with typing requirement
        from tkinter import simpledialog
        confirmation = simpledialog.askstring(
            "⚠️ Confirm Delete - Step 2/2",
            f"To confirm deletion, type the panel name:\n\n"
            f"{file_name}\n\n"
            f"Type it exactly (case-sensitive):",
            parent=self.parent
        )

        if confirmation != file_name:
            messagebox.showinfo(
                "Deletion Cancelled",
                "Panel name did not match. Deletion cancelled."
            )
            return

        # Perform deletion
        try:
            file_path.unlink()
            messagebox.showinfo(
                "Panel Deleted",
                f"✅ Panel '{file_name}' has been deleted.\n\n"
                f"⚠️ IMPORTANT:\n"
                f"• Update the main tab file to remove imports\n"
                f"• Remove panel initialization code\n"
                f"• Restart the application"
            )
            self.refresh_tabs_tree()
            self.selected_tree_item = None
            self.selected_info_label.config(text="Panel deleted - select another item")
        except Exception as e:
            messagebox.showerror("Deletion Failed", f"Failed to delete panel: {e}")

    def load_settings(self):
        """Load settings from file"""
        settings = {}
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                logger_util.log_message("SETTINGS: Settings file loaded successfully.")
            except Exception as e:
                logger_util.log_message(f"SETTINGS ERROR: Error loading settings: {e}")
            
        # Load tab visibility settings into tk.BooleanVars
        for display_name, setting_key in [
            ("Training Tab", "training_tab_enabled"),
            ("Models Tab", "models_tab_enabled"),
            ("Settings Tab", "settings_tab_enabled"),
            ("Custom Code Tab", "custom_code_tab_enabled"),
        ]:
            # Initialize var if not already done (e.g., in __init__)
            if setting_key not in self.tab_enabled_vars:
                self.tab_enabled_vars[setting_key] = tk.BooleanVar()
            self.tab_enabled_vars[setting_key].set(settings.get(setting_key, True)) # Default to enabled

            self.reorder_mode.set(settings.get('reorder_mode', 'static')) # Default to static

        # Load ToDos
        try:
            self.todos = settings.get('todos', { 'tasks': [], 'bugs': [], 'completed': [] })
        except Exception:
            self.todos = { 'tasks': [], 'bugs': [], 'completed': [] }

        return settings

    def save_settings_to_file(self):
        """Save current settings to file, preserving other sections."""
        log_message("SETTINGS: Saving all settings to file.")
        try:
            # Read existing settings to preserve other sections (like runner_defaults)
            all_settings = {}
            if self.settings_file.exists():
                try:
                    with open(self.settings_file, 'r') as f:
                        all_settings = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    log_message(f"SETTINGS ERROR: Could not read existing settings file for merge: {e}")

            # Update the settings managed by this tab
            all_settings.update({
                'default_epochs': self.default_epochs.get(),
                'default_batch': self.default_batch.get(),
                'default_learning_rate': self.default_lr.get(),
                'auto_refresh_models': self.auto_refresh.get(),
                'show_debug': self.show_debug.get(),
                'confirm_training': self.confirm_training.get(),
                'max_cpu_threads': self.max_cpu_threads.get(),
                'max_ram_percent': self.max_ram_percent.get(),
                'max_seq_length': self.max_seq_length.get(),
                'gradient_accumulation': self.gradient_accumulation.get()
            })
            
            # Save tab visibility settings
            for setting_key, var in self.tab_enabled_vars.items():
                all_settings[setting_key] = var.get()

            # Save tab reordering setting
            all_settings['reorder_mode'] = self.reorder_mode.get()

            # Ensure custom_code_tab is in tab_order if it's enabled
            tab_order = self.settings.get('tab_order', ['training_tab', 'models_tab', 'custom_code_tab', 'settings_tab'])
            if 'custom_code_tab' not in tab_order and self.tab_enabled_vars.get('custom_code_tab_enabled', tk.BooleanVar(value=False)).get():
                # Insert custom_code_tab before settings_tab if enabled
                if 'settings_tab' in tab_order:
                    idx = tab_order.index('settings_tab')
                    tab_order.insert(idx, 'custom_code_tab')
                else:
                    tab_order.append('custom_code_tab')
            all_settings['tab_order'] = tab_order

            # Save Regression Policy
            if not hasattr(self, 'policy_alert_drop'):
                # Initialize defaults if UI not visited
                self.policy_enabled = tk.BooleanVar(value=True)
                self.policy_alert_drop = tk.DoubleVar(value=5.0)
                self.policy_strict_block = tk.BooleanVar(value=False)
                self.policy_auto_rollback = tk.BooleanVar(value=False)
            all_settings['regression_policy'] = {
                'enabled': self.policy_enabled.get(),
                'alert_drop_percent': float(self.policy_alert_drop.get()),
                'strict_block': self.policy_strict_block.get(),
                'auto_rollback': self.policy_auto_rollback.get()
            }

            # If caller populated panel_orders in memory, persist it
            if 'panel_orders' in self.settings:
                all_settings['panel_orders'] = self.settings.get('panel_orders', {})

            # Persist ToDos
            try:
                all_settings['todos'] = getattr(self, 'todos', { 'tasks': [], 'bugs': [], 'completed': [] })
                all_settings['todo_show_on_launch'] = bool(self.todo_show_on_launch.get()) if hasattr(self, 'todo_show_on_launch') else False
            except Exception:
                pass

            with open(self.settings_file, 'w') as f:
                json.dump(all_settings, f, indent=2)

            log_message("SETTINGS: Settings saved successfully.")
            messagebox.showinfo("Settings Saved", "Settings have been saved successfully!")
            self.settings = all_settings
        except Exception as e:
            log_message(f"SETTINGS ERROR: Failed to save settings: {e}")
            messagebox.showerror("Save Error", f"Failed to save settings: {e}")

    # --- ToDo List: Handlers ---
    def refresh_todo_view(self):
        """Refresh main todo tree view from file-based storage."""
        # Clear tree
        for item in self.todo_tree.get_children():
            self.todo_tree.delete(item)

        # Roots
        tasks_root = self.todo_tree.insert('', 'end', text='🗒 Tasks', open=True)
        bugs_root = self.todo_tree.insert('', 'end', text='🐞 Bugs', open=True)
        work_root = self.todo_tree.insert('', 'end', text='📋 Work-Orders', open=True)
        notes_root = self.todo_tree.insert('', 'end', text='📝 Notes', open=True)
        completed_root = self.todo_tree.insert('', 'end', text='✅ Completed', open=True)

        # Priority tag styles
        try:
            self.todo_tree.tag_configure('prio_high', foreground='#ff5555')
            self.todo_tree.tag_configure('prio_med', foreground='#ff9900')
            self.todo_tree.tag_configure('prio_low', foreground='#ffd700')
            self.todo_tree.tag_configure('completed', foreground='#33cc33', font=('Arial', 9, 'italic'))
        except Exception:
            pass

        # Helper to sort by priority
        def _prio_key(item):
            p = (item or {}).get('priority', 'low').lower()
            return {'high': 0, 'medium': 1, 'low': 2}.get(p, 2)

        # Load from files and populate
        tcount = bcount = wcount = ncount = 0
        ph = pm = pl = 0

        # Tasks
        try:
            task_files = list_todo_files('tasks')
            tasks_data = [read_todo_file(f) for f in task_files]
            for todo in sorted(tasks_data, key=_prio_key):
                text = self._format_todo_display_text(todo, 'tasks')
                pr = (todo.get('priority', 'low') or 'low').lower()
                tag = ('prio_high',) if pr == 'high' else (('prio_med',) if pr == 'medium' else ('prio_low',))
                self.todo_tree.insert(tasks_root, 'end', iid=f'tasks:{todo["filename"]}', text=text, values=('☐',), tags=tag)
                tcount += 1
                if pr == 'high':
                    ph += 1
                elif pr == 'medium':
                    pm += 1
                else:
                    pl += 1
        except Exception as e:
            log_message(f"SETTINGS: Error loading tasks: {e}")

        # Bugs
        try:
            bug_files = list_todo_files('bugs')
            bugs_data = [read_todo_file(f) for f in bug_files]
            for todo in sorted(bugs_data, key=_prio_key):
                text = self._format_todo_display_text(todo, 'bugs')
                pr = (todo.get('priority', 'low') or 'low').lower()
                tag = ('prio_high',) if pr == 'high' else (('prio_med',) if pr == 'medium' else ('prio_low',))
                self.todo_tree.insert(bugs_root, 'end', iid=f'bugs:{todo["filename"]}', text=text, values=('☐',), tags=tag)
                bcount += 1
                if pr == 'high':
                    ph += 1
                elif pr == 'medium':
                    pm += 1
                else:
                    pl += 1
        except Exception as e:
            log_message(f"SETTINGS: Error loading bugs: {e}")

        # Work Orders
        try:
            work_files = list_todo_files('work_orders')
            work_data = [read_todo_file(f) for f in work_files]
            for todo in sorted(work_data, key=_prio_key):
                text = self._format_todo_display_text(todo, 'work_orders')
                pr = (todo.get('priority', 'low') or 'low').lower()
                tag = ('prio_high',) if pr == 'high' else (('prio_med',) if pr == 'medium' else ('prio_low',))
                self.todo_tree.insert(work_root, 'end', iid=f'work_orders:{todo["filename"]}', text=text, values=('☐',), tags=tag)
                wcount += 1
                if pr == 'high':
                    ph += 1
                elif pr == 'medium':
                    pm += 1
                else:
                    pl += 1
        except Exception as e:
            log_message(f"SETTINGS: Error loading work orders: {e}")

        # Notes
        try:
            note_files = list_todo_files('notes')
            notes_data = [read_todo_file(f) for f in note_files]
            for todo in sorted(notes_data, key=_prio_key):
                text = self._format_todo_display_text(todo, 'notes')
                pr = (todo.get('priority', 'low') or 'low').lower()
                tag = ('prio_high',) if pr == 'high' else (('prio_med',) if pr == 'medium' else ('prio_low',))
                self.todo_tree.insert(notes_root, 'end', iid=f'notes:{todo["filename"]}', text=text, values=('☐',), tags=tag)
                ncount += 1
                if pr == 'high':
                    ph += 1
                elif pr == 'medium':
                    pm += 1
                else:
                    pl += 1
        except Exception as e:
            log_message(f"SETTINGS: Error loading notes: {e}")

        # Completed
        ccount = 0
        try:
            completed_files = list_todo_files('completed')
            completed_data = [read_todo_file(f) for f in completed_files]
            for todo in completed_data:
                row_category = todo.get('category', 'completed')
                text = self._format_todo_display_text(todo, row_category)
                self.todo_tree.insert(completed_root, 'end', iid=f'completed:{todo["filename"]}', text=text, values=('☑',), tags=('completed',))
                ccount += 1
        except Exception as e:
            log_message(f"SETTINGS: Error loading completed: {e}")

        # Update header counts with priority totals (two-line layout)
        self.todo_counts_var.set(f"Tasks: {tcount} | Bugs: {bcount} | Work-Orders: {wcount} | Notes: {ncount} | Completed: {ccount}")
        self.todo_priority_var.set(f"Priority: High {ph} | Medium {pm} | Low {pl}")
        # Update buttons state
        self._apply_todo_button_states()

    def _on_todo_click(self, event):
        """Handle click on todo item - file-based storage doesn't use 'done' checkboxes."""
        # With file-based storage, items are either active or completed (in different folders)
        # No need for inline checkbox toggling
        pass

    def _get_selected_todo(self):
        """Get selected todo from tree - returns (category, filename)."""
        sel = self.todo_tree.selection()
        if not sel:
            return None
        item = sel[0]
        if ':' not in item:
            return None
        category, filename = item.split(':', 1)
        return category, filename

    def _is_todo_actionable(self, action):
        """Check if action is valid for selected todo."""
        sel = self._get_selected_todo()
        if not sel:
            return False
        category, filename = sel
        if action == 'mark':
            return category in ('tasks', 'bugs', 'work_orders', 'notes')
        if action == 'edit':
            return category in ('tasks', 'bugs', 'work_orders', 'notes')
        if action == 'delete':
            return category in ('tasks', 'bugs', 'work_orders', 'notes', 'completed')
        return True

    def _apply_todo_button_states(self):
        for action, btn in (
            ('mark', self.todo_btn_mark),
            ('edit', self.todo_btn_edit),
            ('delete', self.todo_btn_delete),
        ):
            actionable = self._is_todo_actionable(action)
            try:
                btn.state(['!disabled'] if actionable else ['disabled'])
            except Exception:
                pass

    def _on_todo_selection_changed(self, event=None):
        self._apply_todo_button_states()
        # Also refresh hover style immediately
        self._update_todo_button_hover_style()

    def _wire_todo_button_hover(self):
        for action, btn in (
            ('mark', self.todo_btn_mark),
            ('edit', self.todo_btn_edit),
            ('delete', self.todo_btn_delete),
        ):
            btn.bind('<Enter>', lambda e, a=action: self._on_todo_btn_enter(a))
            btn.bind('<Leave>', lambda e, a=action: self._on_todo_btn_leave(a))

    def _on_todo_btn_enter(self, action):
        actionable = self._is_todo_actionable(action)
        btn = {
            'mark': self.todo_btn_mark,
            'edit': self.todo_btn_edit,
            'delete': self.todo_btn_delete,
        }.get(action)
        if not btn:
            return
        try:
            btn.configure(style='Action.TButton' if actionable else 'Select.TButton')
        except Exception:
            pass

    def _on_todo_btn_leave(self, action):
        # Revert to selection-based style
        self._update_todo_button_hover_style()

    def _update_todo_button_hover_style(self):
        for action, btn in (
            ('mark', self.todo_btn_mark),
            ('edit', self.todo_btn_edit),
            ('delete', self.todo_btn_delete),
        ):
            actionable = self._is_todo_actionable(action)
            try:
                btn.configure(style='Action.TButton' if actionable else 'Select.TButton')
            except Exception:
                pass

    def _get_todo_project_selector_data(self) -> tuple[list[str], dict[str, Optional[str]]]:
        """Build dropdown values for manual project selection."""
        values: list[str] = ["[Main ToDo List]"]
        mapping: dict[str, Optional[str]] = {"[Main ToDo List]": None}

        def _append_option(label: str, project_name: Optional[str]):
            display = label
            if display in mapping and project_name:
                suffix = project_name[:6]
                display = f"{display} · {suffix}"
            if display not in mapping:
                mapping[display] = project_name
                values.append(display)

        try:
            for project_dir in list_all_projects_with_todos():
                _append_option(project_dir, project_dir)
        except Exception as exc:
            log_message(f"SETTINGS: Unable to list project todos: {exc}")

        if get_living_project_manager:
            try:
                manager = get_living_project_manager()
                active_projects = manager.list_active_projects() if manager else []
            except Exception as exc:
                log_message(f"SETTINGS: Unable to list Living Projects: {exc}")
                active_projects = []
            for proj in active_projects:
                name = proj.get('name') or proj.get('id') or 'Unnamed Project'
                status = (proj.get('status') or '').lower()
                label = f"{name} — {status}" if status and status not in ('planning', 'in_progress') else name
                _append_option(label, proj.get('name') or proj.get('id'))

        return values, mapping

    def _open_project_todo_from_main_selector(self):
        """Open the selected project todo view from the quick selector."""
        selection = getattr(self, 'todo_project_var', None)
        mapping = getattr(self, 'todo_project_selector_map', {})
        selected_label = selection.get() if selection else None
        project_name = mapping.get(selected_label)
        if project_name:
            self.current_project_context = project_name
            self.show_project_todo_popup(project_name)
        else:
            self.show_todo_popup()

    def _resolve_living_project_id(self, manager, identifier: Optional[str]) -> Optional[str]:
        """Best-effort resolution of a Living Project ID from name or id."""
        if not identifier:
            return None
        try:
            project = manager.load_project(identifier)
            if project:
                return getattr(project, 'id', identifier)
        except Exception:
            pass
        try:
            for entry in manager.list_all_projects():
                if identifier in (entry.get('id'), entry.get('name')):
                    return entry.get('id')
        except Exception as exc:
            log_message(f"SETTINGS: Unable to resolve Living Project ID for {identifier}: {exc}")
        return None

    def _link_todo_to_living_project(self, project_identifier: Optional[str], todo_path: Path):
        """Link a todo file to a Living Project if possible."""
        if not project_identifier or not get_living_project_manager:
            return
        try:
            manager = get_living_project_manager()
            if not manager:
                return
            project_id = self._resolve_living_project_id(manager, project_identifier)
            if project_id:
                manager.link_todo(project_id, str(todo_path))
        except Exception as exc:
            log_message(f"SETTINGS: Failed to link todo to Living Project {project_identifier}: {exc}")

    def _on_todo_show_on_launch_changed(self):
        # Persist immediately
        try:
            self.save_settings_to_file()
        except Exception:
            pass

    # Optional popup on launch
    def show_todo_popup(self, project_name: str = None, prefer_project: bool = False, auto_open_create: bool = False):
        """Show main todo popup.

        If project_name is provided and prefer_project is True, open the Project ToDo view instead.
        """
        # Redirect to project view if requested
        try:
            ctx_project = project_name or getattr(self, 'current_project_context', None)
            if prefer_project and ctx_project:
                return self.show_project_todo_popup(ctx_project)
        except Exception:
            pass
        agent_role_choices = ['general', 'coder', 'debugger', 'researcher', 'planner']
        agent_role_display = {role: role.title() for role in agent_role_choices}
        agent_role_lookup = {display: role for role, display in agent_role_display.items()}

        top = tk.Toplevel(self.root)
        top.title("ToDo List")
        try:
            geom = (self.settings or {}).get('todo_geometry_main')
            if isinstance(geom, str) and 'x' in geom:
                top.geometry(geom)
            else:
                top.geometry('820x560')
        except Exception:
            top.geometry('820x560')
        try:
            top.transient(self.root)
            top.lift()
            top.attributes('-topmost', True)
            # Drop always-on-top shortly after so normal stacking resumes
            self.root.after(500, lambda: top.attributes('-topmost', False))
            top.focus_force()
        except Exception:
            pass
        # Track active state so other tabs can show an indicator
        try:
            self.todo_popup_active = True
            self._active_todo_popup_window = top  # Phase Sub-Zero-D: Track window for dock refresh
            def _on_close():
                # PHASE SUB-ZERO-D: Stop planner log refresh
                try:
                    self._stop_planner_log_refresh()
                except Exception:
                    pass

                # Persist window geometry silently
                try:
                    w = max(400, int(top.winfo_width()))
                    h = max(300, int(top.winfo_height()))
                    self.settings['todo_geometry_main'] = f"{w}x{h}"
                    # Merge minimal write
                    all_settings = {}
                    if self.settings_file.exists():
                        try:
                            with open(self.settings_file, 'r') as f:
                                all_settings = json.load(f)
                        except Exception:
                            all_settings = {}
                    all_settings['todo_geometry_main'] = self.settings['todo_geometry_main']
                    with open(self.settings_file, 'w') as f:
                        json.dump(all_settings, f, indent=2)
                except Exception:
                    pass
                try:
                    self.todo_popup_active = False
                except Exception:
                    pass
                try:
                    # Clear active popup reference
                    self._active_todo_popup_window = None
                except Exception:
                    pass
                try:
                    top.destroy()
                except Exception:
                    pass
            top.protocol('WM_DELETE_WINDOW', _on_close)
            top.bind('<Destroy>', lambda e: setattr(self, 'todo_popup_active', False))
        except Exception:
            pass
        frame = ttk.Frame(top)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=0)
        frame.rowconfigure(2, weight=1)

        # Toggle header: allow switching to Project list when context is provided
        popup_project_values, popup_project_map = self._get_todo_project_selector_data()
        popup_project_var = tk.StringVar(value=self.todo_project_var.get() if isinstance(getattr(self, 'todo_project_var', None), tk.StringVar) else (popup_project_values[0] if popup_project_values else "[Main ToDo List]"))

        # Preselect incoming project context if provided
        incoming_project = project_name or getattr(self, 'current_project_context', None)
        if incoming_project:
            for label, proj in popup_project_map.items():
                if proj == incoming_project:
                    popup_project_var.set(label)
                    break

        def _open_selected_project():
            selection = popup_project_var.get()
            target = popup_project_map.get(selection) or incoming_project
            if not target:
                messagebox.showinfo("Select Project", "Choose a project from the dropdown first.", parent=top)
                return
            try:
                top.destroy()
            except Exception:
                pass
            self.current_project_context = target
            self.show_project_todo_popup(target)

        log_message("TODO POPUP: Building header toggle row (Main)...")
        toggle = ttk.Frame(frame)
        toggle.grid(row=0, column=0, columnspan=2, sticky=tk.EW)
        try:
            for c in range(3):
                toggle.columnconfigure(c, weight=1)
            # [+Plan] button opens legacy manual plan creation dialog
            plan_btn = ttk.Button(toggle, text='＋ Plan', style='Action.TButton', command=lambda: self._open_plan_template_dialog(None))
            plan_btn.grid(row=0, column=0, sticky=tk.W, padx=(0,8))
            main_btn = ttk.Button(toggle, text='Main ToDo List', style='Action.TButton')
            main_btn.grid(row=0, column=1, sticky=tk.EW, padx=(0,4))
            proj_btn = ttk.Button(toggle, text='Project ToDo List', style='Select.TButton', command=_open_selected_project)
            proj_btn.grid(row=0, column=2, sticky=tk.EW, padx=(4,0))

            selector = ttk.Frame(toggle)
            selector.grid(row=1, column=0, columnspan=3, sticky=tk.EW, pady=(4, 0))
            selector.columnconfigure(1, weight=1)
            ttk.Label(selector, text='Project:', style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W)
            popup_combo = ttk.Combobox(
                selector,
                textvariable=popup_project_var,
                values=popup_project_values,
                state='readonly'
            )
            popup_combo.grid(row=0, column=1, sticky=tk.EW, padx=(6, 6))
            ttk.Button(selector, text='Open Selected', style='Select.TButton', command=_open_selected_project).grid(row=0, column=2, sticky=tk.E)
            popup_combo.bind('<<ComboboxSelected>>', lambda e: _refresh_project_preview())
            try:
                if isinstance(getattr(self, 'todo_project_var', None), tk.StringVar):
                    def _sync_help_selector(*_):
                        try:
                            popup_project_var.set(self.todo_project_var.get())
                            _refresh_project_preview()
                        except Exception:
                            pass
                    self.todo_project_var.trace_add('write', _sync_help_selector)
            except Exception:
                pass
        except Exception as e:
            log_message(f"TODO POPUP: Header build error (Main): {e}")

        # Top right header buttons
        def open_system_trash():
            try:
                import platform, subprocess, os, shutil
                system = platform.system()
                if system == 'Linux':
                    if shutil.which('gio'):
                        subprocess.Popen(['gio', 'open', 'trash:///'])
                    elif shutil.which('xdg-open'):
                        subprocess.Popen(['xdg-open', os.path.expanduser('~/.local/share/Trash/files')])
                elif system == 'Darwin':
                    subprocess.Popen(['open', os.path.expanduser('~/.Trash')])
                elif system == 'Windows':
                    subprocess.Popen(['explorer', 'shell:RecycleBinFolder'])
            except Exception:
                pass

        try:
            trash_btn = ttk.Button(frame, text='🗑', width=3, command=open_system_trash)
            trash_btn.grid(row=0, column=1, sticky=tk.NE, padx=(6,0))
        except Exception:
            pass

        # Plan context (used to auto-link new todos to a selected plan)
        plan_context = {'name': None}

        # Two-line header for better fit
        try:
            ttk.Label(frame, textvariable=self.todo_counts_var, font=("Arial", 11, "bold"), style='CategoryPanel.TLabel', anchor='center').grid(row=1, column=0, sticky=tk.EW)
            ttk.Label(frame, textvariable=self.todo_priority_var, font=("Arial", 10), style='CategoryPanel.TLabel', anchor='center').grid(row=2, column=0, sticky=tk.EW, pady=(0,6))
        except Exception as e:
            log_message(f"TODO POPUP: Counts row error (Main): {e}")

        # Folder button to open todos directory in file manager
        def open_todos_folder():
            """Open the todos directory in system file manager."""
            try:
                import subprocess
                import platform

                todos_path = str(TODOS_DIR)
                log_message(f"SETTINGS: Opening todos folder: {todos_path}")

                system = platform.system()
                if system == 'Linux':
                    subprocess.Popen(['xdg-open', todos_path])
                elif system == 'Darwin':  # macOS
                    subprocess.Popen(['open', todos_path])
                elif system == 'Windows':
                    subprocess.Popen(['explorer', todos_path])
                else:
                    messagebox.showinfo("Unsupported OS", f"Please manually navigate to:\n{todos_path}", parent=top)
            except Exception as e:
                log_message(f"SETTINGS: Error opening todos folder: {e}")
                messagebox.showerror("Error", f"Failed to open folder:\n{e}\n\nPath: {TODOS_DIR}", parent=top)

        try:
            folder_btn = ttk.Button(frame, text="📁", command=open_todos_folder, width=3)
            folder_btn.grid(row=1, column=1, rowspan=2, sticky=tk.NE, padx=(6,0))
        except Exception as e:
            log_message(f"TODO POPUP: Folder button error (Main): {e}")
        # Phase Sub-Zero-D: VERTICAL PanedWindow layout for tree/details/planner dock
        log_message("TODO POPUP: Building VERTICAL PanedWindow layout (Main)...")

        # Create VERTICAL PanedWindow: tree above details above planner dock
        content_pane = tk.PanedWindow(frame, orient=tk.VERTICAL, sashrelief=tk.RAISED, sashwidth=4, bg='#2b2b2b')
        content_pane.grid(row=3, column=0, columnspan=2, sticky=tk.NSEW)
        frame.rowconfigure(3, weight=1)  # PanedWindow gets all expansion weight

        # ===== PANE 1: TODO Tree (Left) =====
        log_message("TODO POPUP: Creating tree pane...")
        try:
            tree_frame = ttk.Frame(content_pane)
            scr = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
            scr.pack(side=tk.RIGHT, fill=tk.Y)
            pop_tree = ttk.Treeview(tree_frame, columns=("done",), show='tree headings')
            pop_tree.heading('#0', text='Item')
            pop_tree.heading('done', text='Done')
            pop_tree.column('done', width=60, anchor=tk.CENTER, stretch=False)
            pop_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            pop_tree.configure(yscrollcommand=scr.set)
            scr.config(command=pop_tree.yview)

            # Tag colors for priorities/completed
            pop_tree.tag_configure('prio_high', foreground='#ff5555')
            pop_tree.tag_configure('prio_med', foreground='#ff9900')
            pop_tree.tag_configure('prio_low', foreground='#ffd700')
            pop_tree.tag_configure('completed', foreground='#33cc33', font=('Arial', 9, 'italic'))

            content_pane.add(tree_frame, minsize=200, stretch="always")
            log_message("TODO POPUP: Tree pane added")
        except Exception as e:
            log_message(f"TODO POPUP: Tree pane error (Main): {e}")

        # ===== PANE 2: Details Editor (Center) =====
        log_message("TODO POPUP: Creating details pane...")
        try:
            details = ttk.Frame(content_pane, padding=4)
            details.columnconfigure(1, weight=1)
            content_pane.add(details, minsize=200, stretch="always")
            log_message("TODO POPUP: Details pane added")
        except Exception as e:
            log_message(f"TODO POPUP: Details pane error (Main): {e}")
        ttk.Label(details, text='Priority', style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W)
        pr_var = tk.StringVar(value='low')
        pr_btns = ttk.Frame(details)
        pr_btns.grid(row=0, column=1, sticky=tk.W, pady=(0,6))
        ttk.Radiobutton(pr_btns, text='High', value='high', variable=pr_var).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(pr_btns, text='Medium', value='medium', variable=pr_var).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(pr_btns, text='Low', value='low', variable=pr_var).pack(side=tk.LEFT, padx=2)
        ttk.Label(details, text='Title', style='CategoryPanel.TLabel').grid(row=1, column=0, sticky=tk.W)
        title_var = tk.StringVar(value='')
        title_entry = ttk.Entry(details, textvariable=title_var)
        title_entry.grid(row=1, column=1, sticky=tk.EW, pady=(0,6))
        ttk.Label(details, text='Assigned Agent', style='CategoryPanel.TLabel').grid(row=2, column=0, sticky=tk.W)
        assigned_row = ttk.Frame(details)
        assigned_row.grid(row=2, column=1, sticky=tk.EW, pady=(0,2))
        assigned_row.columnconfigure(0, weight=1)
        assigned_agent_var = tk.StringVar(value='[Unassigned]')
        assigned_agent_combo = ttk.Combobox(assigned_row, textvariable=assigned_agent_var, state='readonly')
        assigned_agent_combo.grid(row=0, column=0, sticky=tk.EW)
        assign_task_btn = ttk.Button(assigned_row, text='Assign Task', style='Action.TButton')
        assign_task_btn.grid(row=0, column=1, padx=(6, 0))
        assign_task_btn.state(['disabled'])
        assigned_agent_lookup: dict[str, Optional[dict]] = {}

        assigned_agent_status_var = tk.StringVar(value='Select an agent to assign this task.')
        assigned_agent_status = ttk.Label(
            details,
            textvariable=assigned_agent_status_var,
            style='CategoryPanel.TLabel',
            wraplength=360,
            justify=tk.LEFT
        )
        assigned_agent_status.grid(row=3, column=1, sticky=tk.W, pady=(0,6))

        plan_links_var = tk.StringVar(value='Linked Plans: None')
        ttk.Label(details, text='Linked Plans', style='CategoryPanel.TLabel').grid(row=4, column=0, sticky=tk.NW)
        ttk.Label(
            details,
            textvariable=plan_links_var,
            style='CategoryPanel.TLabel',
            wraplength=360,
            justify=tk.LEFT
        ).grid(row=4, column=1, sticky=tk.W, pady=(0,6))
        ttk.Label(details, text='Details', style='CategoryPanel.TLabel').grid(row=5, column=0, sticky=tk.W)
        details_txt = scrolledtext.ScrolledText(details, height=8, wrap=tk.WORD, font=('Arial', 9), bg='#1e1e1e', fg='#dcdcdc')
        details_txt.grid(row=5, column=1, sticky=tk.NSEW)
        details.rowconfigure(5, weight=1)

        def _update_assigned_agent_status() -> None:
            label = assigned_agent_var.get()
            entry = assigned_agent_lookup.get(label)
            if entry and entry is not None and not entry.get('_unavailable'):
                role = (entry.get('role') or 'general').title()
                assigned_agent_status_var.set(f"Assigned to {entry['name']} ({role})")
                assign_task_btn.state(['!disabled'])
            else:
                if label == '[No agents configured]':
                    assigned_agent_status_var.set('No agents configured in the Agents tab yet; add one to enable assignments.')
                elif label == '[Unassigned]':
                    assigned_agent_status_var.set('Select an agent and click Assign Task to dispatch this todo.')
                else:
                    assigned_agent_status_var.set('Previously assigned agent is no longer configured; choose another agent to reassign.')
                assign_task_btn.state(['disabled'])

        def _refresh_assigned_agent_options(preferred_name: Optional[str] = None, preferred_role: Optional[str] = None) -> None:
            assigned_agent_lookup.clear()
            agents = self._collect_assignable_agents()
            options: list[str] = []
            has_agents = bool(agents)
            if has_agents:
                assigned_agent_lookup['[Unassigned]'] = None
                options.append('[Unassigned]')
                for entry in agents:
                    name = entry.get('name')
                    if not name:
                        continue
                    role = (entry.get('role') or 'general').strip().lower()
                    label = f"{name} ({role.title()})"
                    assigned_agent_lookup[label] = {'name': name, 'role': role}
                    options.append(label)
            target_label = '[Unassigned]' if has_agents else '[No agents configured]'
            if preferred_name:
                match_label = None
                for label, entry in assigned_agent_lookup.items():
                    if entry and entry.get('name') == preferred_name:
                        match_label = label
                        break
                if match_label:
                    target_label = match_label
                elif preferred_name:
                    role_display = (preferred_role or 'general').title()
                    unavailable_label = f"{preferred_name} ({role_display}) [Unavailable]"
                    assigned_agent_lookup[unavailable_label] = {'name': preferred_name, 'role': (preferred_role or 'general').lower(), '_unavailable': True}
                    if has_agents:
                        options.append(unavailable_label)
                    else:
                        options = [unavailable_label]
                    target_label = unavailable_label

            if has_agents:
                assigned_agent_combo['values'] = options
                assigned_agent_combo.state(['!disabled'])
            else:
                assigned_agent_combo['values'] = ('[No agents configured]',)
                assigned_agent_combo.state(['disabled'])
                assigned_agent_lookup['[No agents configured]'] = None
            assigned_agent_var.set(target_label)
            _update_assigned_agent_status()

        def _assign_selected_todo_to_agent(project_ctx: str | None = None):
            sel = get_sel_from_pop()
            if not sel:
                messagebox.showinfo("Select Todo", "Select a todo before assigning it to an agent.", parent=top)
                return
            category, filename = sel
            if category == 'completed':
                messagebox.showinfo("Completed Todo", "Completed todos cannot be assigned.", parent=top)
                return
            entry = assigned_agent_lookup.get(assigned_agent_var.get())
            if not entry or entry is None or entry.get('_unavailable'):
                messagebox.showinfo("No Agent", "Please select a configured agent before assigning.", parent=top)
                return
            agent_name = entry.get('name')
            if not agent_name:
                messagebox.showinfo("No Agent", "Please select a configured agent before assigning.", parent=top)
                return
            record = self._build_assignment_record(category, filename, project_ctx)
            if not record:
                messagebox.showerror("Missing Todo", "Unable to load the selected todo file.", parent=top)
                return
            if self._assign_todo_via_agents_dock(record, agent_name):
                refresh_pop()
                populate_details_from_sel()

        assign_task_btn.configure(command=lambda: _assign_selected_todo_to_agent(None))
        assigned_agent_combo.bind('<<ComboboxSelected>>', lambda _e: _update_assigned_agent_status())
        _refresh_assigned_agent_options()

        # Phase Sub-Zero-D: Legacy project preview pane REMOVED (was causing 3-minute startup delay)
        # This functionality is replaced by the "Open Full Project View" button in the header
        # Original code preserved below for reference (commented out):

        # # Inline Project Preview (dual view)
        # project_preview = ttk.LabelFrame(frame, text='Project ToDos (Preview)', padding=8)
        # project_preview.grid(row=7, column=0, columnspan=2, sticky=tk.NSEW, pady=(10, 4))
        # frame.rowconfigure(7, weight=1)
        # project_preview.columnconfigure(0, weight=1)
        # project_preview.rowconfigure(1, weight=1)
        # project_preview_counts = tk.StringVar(value="Select a project to preview its tasks.")
        # ttk.Label(project_preview, textvariable=project_preview_counts, style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W)
        # preview_tree_frame = ttk.Frame(project_preview)
        # preview_tree_frame.grid(row=1, column=0, sticky=tk.NSEW, pady=(4, 6))
        # preview_tree_frame.columnconfigure(0, weight=1)
        # preview_tree_frame.rowconfigure(0, weight=1)
        # preview_scroll = ttk.Scrollbar(preview_tree_frame, orient=tk.VERTICAL)
        # preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        # project_preview_tree = ttk.Treeview(preview_tree_frame, columns=("done",), show='tree headings')
        # project_preview_tree.heading('#0', text='Project Items')
        # project_preview_tree.heading('done', text='Done')
        # project_preview_tree.column('done', width=60, anchor=tk.CENTER, stretch=False)
        # project_preview_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # project_preview_tree.configure(yscrollcommand=preview_scroll.set)
        # preview_scroll.config(command=project_preview_tree.yview)
        # project_preview_tree.tag_configure('prio_high', foreground='#ff5555')
        # project_preview_tree.tag_configure('prio_med', foreground='#ff9900')
        # project_preview_tree.tag_configure('prio_low', foreground='#ffd700')
        # project_preview_tree.tag_configure('completed', foreground='#33cc33', font=('Arial', 9, 'italic'))
        # project_preview_tree.bind('<Double-1>', lambda e: _open_selected_project())

        # Phase Sub-Zero-D: Stub _refresh_project_preview() - no longer needed without preview pane
        def _refresh_project_preview():
            """Legacy function - no-op since project preview pane was removed."""
            pass

        # # Original _refresh_project_preview() code (commented out):
        # def _refresh_project_preview():
        #     sel_label = popup_project_var.get()
        #     project_target = popup_project_map.get(sel_label)
        #     for node in project_preview_tree.get_children():
        #         project_preview_tree.delete(node)
        #     if not project_target:
        #         project_preview_counts.set("Select a project to preview its tasks.")
        #         return
        #     def _prio_key(todo_dict):
        #         p = (todo_dict or {}).get('priority', 'low').lower()
        #         return {'high': 0, 'medium': 1, 'low': 2}.get(p, 2)
        #     cats = [
        #         ('tasks', '🗒 Tasks'),
        #         ('bugs', '🐞 Bugs'),
        #         ('work_orders', '📋 Work-Orders'),
        #         ('notes', '📝 Notes'),
        #         ('completed', '✅ Completed')
        #     ]
        #     roots = {}
        #     for key, label in cats:
        #         roots[key] = project_preview_tree.insert('', 'end', text=label, open=True)
        #     tcount = bcount = wcount = ncount = ccount = 0
        #     ph = pm = pl = 0
        #     for category in ('tasks', 'bugs', 'work_orders', 'notes', 'completed'):
        #         try:
        #             files = list_project_todo_files(project_target, category)
        #             todos = [read_todo_file(f) for f in files]
        #             for todo in sorted(todos, key=_prio_key):
        #                 pr = (todo.get('priority', 'low') or 'low').lower()
        #                 tag = ('prio_high',) if pr == 'high' else (('prio_med',) if pr == 'medium' else ('prio_low',))
        #                 done_flag = '☑' if category == 'completed' else '☐'
        #                 display_text = self._format_todo_display_text(todo, category)
        #                 project_preview_tree.insert(roots[category], 'end', text=display_text, values=(done_flag,), tags=('completed',) if category == 'completed' else tag)
        #                 if category == 'tasks':
        #                     tcount += 1
        #                 elif category == 'bugs':
        #                     bcount += 1
        #                 elif category == 'work_orders':
        #                     wcount += 1
        #                 elif category == 'notes':
        #                     ncount += 1
        #                 elif category == 'completed':
        #                     ccount += 1
        #                 if pr == 'high':
        #                     ph += 1
        #                 elif pr == 'medium':
        #                     pm += 1
        #                 else:
        #                     pl += 1
        #         except Exception as exc:
        #             log_message(f"SETTINGS: Project preview load error ({category}): {exc}")
        #     project_preview_counts.set(
        #         f"{project_target}: Tasks {tcount} | Bugs {bcount} | Work-Orders {wcount} | Notes {ncount} | Completed {ccount} "
        #         f"(High {ph} / Medium {pm} / Low {pl})"
        #     )

        # # "Open Full Project View" button also removed - use header dropdown instead
        # ttk.Button(
        #     project_preview,
        #     text='Open Full Project View',
        #     style='Select.TButton',
        #     command=_open_selected_project
        # ).grid(row=2, column=0, sticky=tk.E, pady=(0, 4))

        def _refresh_after_plan_change():
            previous_selection = get_sel_from_pop()
            try:
                self.refresh_todo_view()
            except Exception:
                pass
            try:
                refresh_pop()
            except Exception:
                pass
            if previous_selection:
                try:
                    pop_tree.selection_set(f"{previous_selection[0]}:{previous_selection[1]}")
                except Exception:
                    pass
            try:
                _refresh_project_preview()
            except Exception:
                pass
            try:
                populate_details_from_sel()
            except Exception:
                pass

        def _handle_plan_mark_complete(plan_filename: str):
            plan_path = TODOS_DIR / 'plans' / plan_filename
            if not plan_path.exists():
                messagebox.showinfo("Select Plan", "Plan file not found. Refresh and try again.", parent=top)
                return
            try:
                plan_data = read_todo_file(plan_path)
            except Exception as exc:
                messagebox.showerror("Error", f"Failed to read plan file:\n{exc}", parent=top)
                return

            plan_title = plan_data.get('title', plan_filename)
            plan_key = (plan_data.get('linked_plan') or '').strip()
            if not plan_key:
                plan_key = self._normalize_plan_key(plan_title)

            open_children, _ = self._collect_plan_children_records(plan_key)
            pending = [c for c in open_children if not c.get('completed')]

            if pending:
                preview_lines = []
                for child in pending[:8]:
                    preview_lines.append(f"- [{child['category']}] {child['title'] or '(Untitled)'}")
                if len(pending) > 8:
                    preview_lines.append(f"... (+{len(pending) - 8} more)")
                message = (
                    f"Plan '{plan_title}' still has {len(pending)} open item(s):\n"
                    + "\n".join(preview_lines)
                    + "\n\nMark every linked todo as complete?"
                )
                if not messagebox.askyesno("Confirm Plan Completion", message, parent=top):
                    return
                for child in pending:
                    try:
                        child_path = child.get('path')
                        if not isinstance(child_path, Path):
                            child_path = Path(child.get('filepath', ''))
                        if child.get('project'):
                            move_project_todo_to_completed(child['project'], child_path)
                        else:
                            move_todo_to_completed(child_path)
                    except Exception as exc:
                        log_message(f"SETTINGS: Failed to complete child todo '{child['title']}': {exc}")
            else:
                if not messagebox.askyesno(
                    "Mark Plan Complete",
                    f"Plan '{plan_title}' has no open todos.\nMark the plan as completed?",
                    parent=top
                ):
                    return

            try:
                move_todo_to_completed(plan_path)
            except Exception as exc:
                messagebox.showerror("Error", f"Failed to mark plan complete:\n{exc}", parent=top)
                return

            _refresh_after_plan_change()
            messagebox.showinfo(
                "Plan Completed",
                f"Plan '{plan_title}' and {len(pending)} linked todo(s) marked complete.",
                parent=top
            )


        # ===== PANE 3: Planner Agent Dock (Bottom - Collapsible) =====
        # Only show if planner agent is published to the active roster via Agents tab → ✓ Set Agent
        log_message("TODO POPUP: Creating planner dock pane...")

        planner_roster_entry = None
        try:
            planner_roster_entry = self._resolve_planner_roster_entry()
            if planner_roster_entry:
                log_message(
                    f"TODO POPUP: Planner roster entry detected name={planner_roster_entry.get('name')} "
                    f"role={planner_roster_entry.get('role')}"
                )
            else:
                log_message("TODO POPUP: ✗ Planner not published via Set Agent (dock hidden)")
        except Exception as e:
            log_message(f"TODO POPUP: Error resolving planner roster entry: {e}")
            if _settings_debug_logger:
                _settings_debug_logger.error("Failed to resolve planner roster entry", exc_info=e)

        has_planner_agent = bool(planner_roster_entry)

        # Dock is visible if: planner exists AND user toggled it expanded
        dock_visible = has_planner_agent and getattr(self, '_planner_dock_visible', False)

        try:
            dock_pane = ttk.Frame(content_pane)

            if dock_visible:
                # EXPANDED STATE: Full planner chat interface (33%)
                log_message("TODO POPUP: Planner dock EXPANDED")
                planner_dock = self._create_planner_dock_section(
                    dock_pane,
                    project_context=project_name or getattr(self, 'current_project_context', None)
                )
                planner_dock.pack(fill=tk.BOTH, expand=True)
                content_pane.add(dock_pane, minsize=300, stretch="always")
            elif has_planner_agent:
                # COLLAPSED STATE: Horizontal toggle bar (5% height) - only if planner agent configured
                log_message("TODO POPUP: Planner dock COLLAPSED (agent available)")
                collapse_container = ttk.Frame(dock_pane, height=30)
                collapse_container.pack(fill=tk.BOTH, expand=True)
                collapse_container.pack_propagate(False)

                # Horizontal expand toggle button
                ttk.Button(
                    collapse_container,
                    text='▼ Expand Planner Agent Dock ▼',
                    command=lambda: self._open_planner_agent_dock(project_name),
                    style='Action.TButton'
                ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=2)

                content_pane.add(dock_pane, minsize=30, height=30, stretch="never")
            else:
                # NO PLANNER AGENT: Don't add dock pane at all
                log_message("TODO POPUP: No planner agent configured - dock hidden")

            log_message("TODO POPUP: Planner dock pane added")
        except Exception as e:
            log_message(f"TODO POPUP: Planner dock pane error (Main): {e}")

        # Set PanedWindow sash positions for VERTICAL layout
        try:
            top.update_idletasks()  # Force geometry calculation
            total_height = content_pane.winfo_height()
            if total_height < 100:  # Not yet sized, use window height
                total_height = max(600, top.winfo_height() - 200)  # Subtract header/button space

            if has_planner_agent:
                # Planner agent configured - 3 panes
                if dock_visible:
                    # EXPANDED: 33% / 33% / 33% (tree / details / planner dock)
                    pos1 = int(total_height * 0.33)
                    pos2 = int(total_height * 0.66)
                    log_message(f"TODO POPUP: VERTICAL sash EXPANDED (33/33/33): {pos1}, {pos2}")
                else:
                    # COLLAPSED: 45% / 50% / 5% (dock minimized)
                    pos1 = int(total_height * 0.45)
                    pos2 = int(total_height * 0.95)
                    log_message(f"TODO POPUP: VERTICAL sash COLLAPSED (45/50/5): {pos1}, {pos2}")
                content_pane.sash_place(0, 0, pos1)
                content_pane.sash_place(1, 0, pos2)
            else:
                # No planner - 2 panes only (tree / details)
                pos1 = int(total_height * 0.50)  # 50/50 split
                log_message(f"TODO POPUP: VERTICAL sash NO PLANNER (50/50): {pos1}")
                content_pane.sash_place(0, 0, pos1)
        except Exception as e:
            log_message(f"TODO POPUP: Sash positioning error: {e}")

        # ===== BUTTON ROW: Link/Merge Plans + Planner Toggle (Row 4) =====
        log_message("TODO POPUP: Creating bottom button row...")

        def _link_plan_cb():
            """Link selected todo to a plan."""
            sel = pop_tree.selection()
            if not sel:
                messagebox.showwarning("No Selection", "Please select a todo item to link to a plan.", parent=top)
                return

            item = sel[0]
            val = pop_tree.item(item)
            if not val.get('values'):
                messagebox.showinfo("Invalid Selection", "Please select an actual todo item, not a category.", parent=top)
                return

            # Get todo info from stored data
            todo_info = getattr(pop_tree.item(item), '_todo_info', None)
            if not todo_info:
                # Try to reconstruct from tree item
                title = val.get('text', '').split(' ', 1)[-1] if val.get('text') else ''
                for cat in ['tasks', 'bugs', 'work_orders', 'notes', 'completed']:
                    files = list_todo_files(cat)
                    for f in files:
                        data = read_todo_file(f)
                        if data.get('title') == title:
                            todo_info = data
                            todo_info['category'] = cat
                            break
                    if todo_info:
                        break

            if not todo_info:
                messagebox.showerror("Missing File", "Unable to locate the selected todo file.", parent=top)
                return
            self._open_link_todo_to_plan_dialog(top, todo_info, lambda: refresh_pop(), None)

        def _merge_plans_cb():
            """Merge multiple plans into one."""
            self._open_merge_plans_dialog(top, lambda: refresh_pop())

        # ===== ROW 5: LINK/MERGE PLANS BUTTONS (always show) =====
        try:
            button_row = ttk.Frame(frame)
            button_row.grid(row=5, column=0, columnspan=2, sticky=tk.EW, pady=(4, 0))
            frame.rowconfigure(5, weight=0)

            # Link/Merge Plans buttons (always show)
            button_row.columnconfigure(0, weight=1)
            button_row.columnconfigure(1, weight=1)
            ttk.Button(button_row, text="🔗 Link to Plan", style='Action.TButton', command=_link_plan_cb).grid(row=0, column=0, sticky=tk.EW, padx=(0, 4))
            ttk.Button(button_row, text="🔀 Merge Plans", style='Select.TButton', command=_merge_plans_cb).grid(row=0, column=1, sticky=tk.EW, padx=(4, 0))

            log_message("TODO POPUP: Link/Merge Plans button row created successfully")
        except Exception as e:
            log_message(f"TODO POPUP: Button row error: {e}")
            if _settings_debug_logger:
                _settings_debug_logger.error("Failed to create button row", exc_info=e)

        # Show helpful instructions on popup open
        try:
            details_txt.insert(tk.END, "📝 Quick Start:\n\n")
            details_txt.insert(tk.END, "1. To CREATE: Fill in Title & Details, set Priority, click 'Create Todo', then select category\n\n")
            if dock_visible:
                details_txt.insert(tk.END, "2. To CREATE PLAN: Use + Plan button above, describe plan in natural language\n\n")
                details_txt.insert(tk.END, "3. To EDIT: Select an item from the list above, modify fields, click 'Save'\n\n")
                details_txt.insert(tk.END, "4. To VIEW: Click any item in the tree to view/edit its details here\n\n")
            else:
                details_txt.insert(tk.END, "2. To EDIT: Select an item from the list above, modify fields, click 'Save'\n\n")
                details_txt.insert(tk.END, "3. To VIEW: Click any item in the tree to view/edit its details here\n\n")
            details_txt.insert(tk.END, "Select an item above to get started!")
            log_message("SETTINGS: Quick Start instructions added to details pane")
        except Exception as e:
            log_message(f"SETTINGS: Error adding Quick Start instructions: {e}")

        # Populate from file-based storage
        def refresh_pop():
            log_message("SETTINGS: refresh_pop() START")
            # Check if popup window and tree still exist
            try:
                if not pop_tree.winfo_exists():
                    log_message("SETTINGS: Popup tree no longer exists, skipping refresh")
                    return
            except Exception:
                log_message("SETTINGS: Popup tree widget destroyed, skipping refresh")
                return

            try:
                for i in pop_tree.get_children():
                    pop_tree.delete(i)
                log_message("SETTINGS: Tree cleared successfully")
            except Exception as e:
                log_message(f"SETTINGS: Error clearing popup tree: {e}")
                return
            try:
                troot = pop_tree.insert('', 'end', text='🗒 Tasks', open=True)
                broot = pop_tree.insert('', 'end', text='🐞 Bugs', open=True)
                wroot = pop_tree.insert('', 'end', text='📋 Work-Orders', open=True)
                nroot = pop_tree.insert('', 'end', text='📝 Notes', open=True)
                croot = pop_tree.insert('', 'end', text='✅ Completed', open=True)
                log_message("SETTINGS: Tree roots created successfully")
            except Exception as e:
                log_message(f"SETTINGS: Error creating popup tree roots: {e}")
                return

            def _prio_key(todo_dict):
                p = (todo_dict or {}).get('priority','low').lower()
                return {'high':0, 'medium':1, 'low':2}.get(p, 2)

            # Load from files instead of JSON
            try:
                task_files = list_todo_files('tasks')
                log_message(f"SETTINGS: Found {len(task_files)} task files")
                tasks_data = [read_todo_file(f) for f in task_files]
                for todo in sorted(tasks_data, key=_prio_key):
                    pr = (todo.get('priority','low') or 'low').lower()
                    tag = ('prio_high',) if pr=='high' else (('prio_med',) if pr=='medium' else ('prio_low',))
                    display_text = self._format_todo_display_text(todo, 'tasks')
                    pop_tree.insert(troot, 'end', iid=f'tasks:{todo["filename"]}', text=display_text, values=('☐',), tags=tag)
                log_message(f"SETTINGS: Populated {len(tasks_data)} tasks")
            except Exception as e:
                log_message(f"SETTINGS: Error populating tasks in popup: {e}")

            try:
                bug_files = list_todo_files('bugs')
                bugs_data = [read_todo_file(f) for f in bug_files]
                for todo in sorted(bugs_data, key=_prio_key):
                    pr = (todo.get('priority','low') or 'low').lower()
                    tag = ('prio_high',) if pr=='high' else (('prio_med',) if pr=='medium' else ('prio_low',))
                    display_text = self._format_todo_display_text(todo, 'bugs')
                    pop_tree.insert(broot, 'end', iid=f'bugs:{todo["filename"]}', text=display_text, values=('☐',), tags=tag)
            except Exception as e:
                log_message(f"SETTINGS: Error populating bugs in popup: {e}")

            try:
                wo_files = list_todo_files('work_orders')
                wo_data = [read_todo_file(f) for f in wo_files]
                for todo in sorted(wo_data, key=_prio_key):
                    pr = (todo.get('priority','low') or 'low').lower()
                    tag = ('prio_high',) if pr=='high' else (('prio_med',) if pr=='medium' else ('prio_low',))
                    display_text = self._format_todo_display_text(todo, 'work_orders')
                    pop_tree.insert(wroot, 'end', iid=f'work_orders:{todo["filename"]}', text=display_text, values=('☐',), tags=tag)
            except Exception as e:
                log_message(f"SETTINGS: Error populating work-orders in popup: {e}")

            try:
                notes_files = list_todo_files('notes')
                notes_data = [read_todo_file(f) for f in notes_files]
                for todo in sorted(notes_data, key=_prio_key):
                    pr = (todo.get('priority','low') or 'low').lower()
                    tag = ('prio_high',) if pr=='high' else (('prio_med',) if pr=='medium' else ('prio_low',))
                    display_text = self._format_todo_display_text(todo, 'notes')
                    pop_tree.insert(nroot, 'end', iid=f'notes:{todo["filename"]}', text=display_text, values=('☐',), tags=tag)
            except Exception as e:
                log_message(f"SETTINGS: Error populating notes in popup: {e}")

            try:
                completed_files = list_todo_files('completed')
                completed_data = [read_todo_file(f) for f in completed_files]
                for todo in completed_data:
                    display_text = self._format_todo_display_text(todo, 'completed')
                    pop_tree.insert(croot, 'end', iid=f'completed:{todo["filename"]}', text=display_text, values=('☑',), tags=('completed',))
            except Exception as e:
                log_message(f"SETTINGS: Error populating completed in popup: {e}")

            # Plans and Tests (optional roots)
            try:
                plans_root = pop_tree.insert('', 'end', text='📐 Plans', open=True)
                plan_files = list_todo_files('plans')
                plans_data = [read_todo_file(f) for f in plan_files]
                for todo in plans_data:
                    pop_tree.insert(plans_root, 'end', iid=f'plans:{todo["filename"]}', text=todo.get('title',''), values=('☐',))
            except Exception as e:
                log_message(f"SETTINGS: Error populating plans in popup: {e}")
            try:
                tests_root = pop_tree.insert('', 'end', text='🧪 Tests', open=True)
                test_files = list_todo_files('tests')
                tests_data = [read_todo_file(f) for f in test_files]
                for todo in tests_data:
                    pop_tree.insert(tests_root, 'end', iid=f'tests:{todo["filename"]}', text=todo.get('title',''), values=('☐',))
            except Exception as e:
                log_message(f"SETTINGS: Error populating tests in popup: {e}")

        # Populate tree first, then bind events
        try:
            refresh_pop()
        except Exception as e:
            log_message(f"TODO POPUP: Initial populate error (Main): {e}")
        try:
            _refresh_project_preview()
        except Exception as e:
            log_message(f"TODO POPUP: Initial project preview error: {e}")

        # Auto-refresh while popup is open to pick up external changes/restores
        last_sig = {'v': 0}
        def _tick_refresh():
            try:
                import os, time
                sig = 0
                for cat in ('tasks','bugs','work_orders','notes','completed'):
                    d = TODOS_DIR / cat
                    if d.exists():
                        sig ^= int(d.stat().st_mtime)
                if sig != last_sig['v']:
                    last_sig['v'] = sig
                    refresh_pop()
            except Exception:
                pass
            try:
                if top.winfo_exists():
                    self.root.after(2000, _tick_refresh)
            except Exception:
                pass
        try:
            self.root.after(2000, _tick_refresh)
        except Exception:
            pass

        # Action buttons use existing handlers but with selected item from popup
        try:
            btns = ttk.Frame(frame)
            btns.grid(row=6, column=0, columnspan=2, sticky=tk.EW, pady=(6,0))
            frame.rowconfigure(6, weight=0)
            frame.rowconfigure(5, weight=0)
        except Exception as e:
            log_message(f"TODO POPUP: Action buttons row error (Main): {e}")
        for i in range(5):
            btns.columnconfigure(i, weight=1)

        def get_sel_from_pop():
            """Returns (category, filename) from selected tree item."""
            sel = pop_tree.selection()
            if not sel:
                return None
            item = sel[0]
            if ':' not in item:
                return None
            category, filename = item.split(':', 1)
            return category, filename

        def populate_details_from_sel():
            """Load todo file and populate detail fields."""
            log_message("SETTINGS: populate_details_from_sel() called")
            sel = get_sel_from_pop()

            # If nothing selected, don't clear the Quick Start instructions
            if not sel:
                log_message("SETTINGS: No selection, keeping Quick Start instructions")
                return

            # Reset fields when we have a selection
            try:
                pr_var.set('low')
                title_var.set('')
                details_txt.delete('1.0', tk.END)
                plan_links_var.set('Linked Plans: None')
                log_message(f"SETTINGS: Fields cleared for selection: {sel}")
            except Exception:
                pass
            _refresh_assigned_agent_options()
            category, filename = sel

            # Don't populate details for completed items (read-only)
            if category == 'completed':
                try:
                    title_var.set('[Completed - Read Only]')
                    details_txt.insert(tk.END, 'Completed items are read-only. Delete to remove or recreate as new todo.')
                    plan_links_var.set('Linked Plans: None')
                except Exception:
                    pass
                return

            # Load from file
            assigned_name = None
            assigned_role = None
            try:
                from pathlib import Path
                todo_dir = TODOS_DIR / category
                filepath = todo_dir / filename
                if not filepath.exists():
                    return

                todo_data = read_todo_file(filepath)
                pr_var.set(todo_data.get('priority', 'low'))
                title_var.set(todo_data.get('title', ''))
                details_txt.insert(tk.END, todo_data.get('details', ''))
                linked_plan_keys = self._extract_linked_plan_keys(todo_data)
                assigned_name = (todo_data.get('assigned_agent') or '').strip() or None
                assigned_role = (todo_data.get('assigned_agent_role') or '').strip().lower() or None
                if category == 'plans':
                    plan_key = (todo_data.get('linked_plan') or '').strip()
                    if not plan_key:
                        plan_key = self._normalize_plan_key(todo_data.get('title'))
                    plan_links_var.set(f"Plan Key: {plan_key or 'None'}")
                    details_txt.insert(tk.END, "\n\nLinked Todos:\n")
                    if plan_key:
                        details_txt.insert(tk.END, self._build_plan_preview_text(plan_key))
                    else:
                        details_txt.insert(tk.END, "No plan key detected.")
                else:
                    if linked_plan_keys:
                        plan_links_var.set(f"Linked Plans: {', '.join(linked_plan_keys)}")
                    else:
                        plan_links_var.set("Linked Plans: None")
            except Exception as e:
                log_message(f"SETTINGS: Error loading todo file: {e}")
                assigned_name = None
                assigned_role = None

            _refresh_assigned_agent_options(assigned_name, assigned_role)

        try:
            pop_tree.bind('<<TreeviewSelect>>', lambda e: populate_details_from_sel())
        except Exception:
            pass
        # Populate details for initial selection if any
        try:
            populate_details_from_sel()
        except Exception:
            pass

        def create_cb():
            """Open a full create dialog to enter category, title, priority, and details."""
            dlg = tk.Toplevel(top)
            dlg.title('Create ToDo')
            dlg.geometry('640x420')
            try:
                dlg.transient(top); dlg.grab_set()
            except Exception:
                pass
            frm = ttk.Frame(dlg, padding=10)
            frm.pack(fill=tk.BOTH, expand=True)
            # Category
            ttk.Label(frm, text='Category', style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W)
            cat_var = tk.StringVar(value='tasks')
            cats = [('Tasks','tasks'),('Bugs','bugs'),('Work-Orders','work_orders'),('Notes','notes')]
            cat_row = ttk.Frame(frm); cat_row.grid(row=0, column=1, sticky=tk.W)
            for label, val in cats:
                ttk.Radiobutton(cat_row, text=label, value=val, variable=cat_var).pack(side=tk.LEFT, padx=4)
            # Priority
            ttk.Label(frm, text='Priority', style='CategoryPanel.TLabel').grid(row=1, column=0, sticky=tk.W)
            pr_local = tk.StringVar(value='low')
            pr_row = ttk.Frame(frm); pr_row.grid(row=1, column=1, sticky=tk.W)
            ttk.Radiobutton(pr_row, text='High', value='high', variable=pr_local).pack(side=tk.LEFT, padx=4)
            ttk.Radiobutton(pr_row, text='Medium', value='medium', variable=pr_local).pack(side=tk.LEFT, padx=4)
            ttk.Radiobutton(pr_row, text='Low', value='low', variable=pr_local).pack(side=tk.LEFT, padx=4)
            # Agent role
            agent_role_create_var = tk.StringVar(value=agent_role_display['general'])
            ttk.Label(frm, text='Agent Type', style='CategoryPanel.TLabel').grid(row=2, column=0, sticky=tk.W)
            agent_role_create_combo = ttk.Combobox(
                frm,
                textvariable=agent_role_create_var,
                values=list(agent_role_display.values()),
                state='readonly'
            )
            agent_role_create_combo.grid(row=2, column=1, sticky=tk.W, pady=(0,2))
            agent_role_create_status_var = tk.StringVar(value=self._get_agent_role_assignment_summary('general')[0])
            agent_role_create_status = ttk.Label(
                frm,
                textvariable=agent_role_create_status_var,
                style='CategoryPanel.TLabel',
                wraplength=360,
                justify=tk.LEFT
            )
            agent_role_create_status.grid(row=3, column=1, sticky=tk.W, pady=(0,8))

            def _update_agent_role_create_status():
                role_key = agent_role_lookup.get(agent_role_create_var.get(), 'general')
                summary, level = self._get_agent_role_assignment_summary(role_key)
                agent_role_create_status_var.set(summary)
                color = "#ffcc66" if level == 'warning' else "#8de0ff"
                try:
                    agent_role_create_status.configure(foreground=color)
                except Exception:
                    pass
            _update_agent_role_create_status()
            agent_role_create_combo.bind('<<ComboboxSelected>>', lambda e: _update_agent_role_create_status())
            # Living Project selector (optional)
            project_var = tk.StringVar(value='[None]')
            project_label = ttk.Label(frm, text='Living Project', style='CategoryPanel.TLabel')
            project_label.grid(row=3, column=0, sticky=tk.W)
            project_row = ttk.Frame(frm)
            project_row.grid(row=3, column=1, sticky=tk.EW, pady=(2, 6))
            project_row.columnconfigure(0, weight=1)
            project_lookup: dict[str, dict] = {}
            lp_manager = None
            project_values: list[str] = ["[None]"]
            if get_living_project_manager:
                try:
                    lp_manager = get_living_project_manager()
                    active_projects = lp_manager.list_active_projects() if lp_manager else []
                except Exception as exc:
                    log_message(f"SETTINGS: Failed to load Living Projects for TODO dialog: {exc}")
                    active_projects = []
            else:
                active_projects = []
            if active_projects:
                for proj in active_projects:
                    name = proj.get('name') or proj.get('id') or 'Unnamed Project'
                    status = proj.get('status', '').lower()
                    display = f"{name}"
                    if status and status not in ('in_progress', 'planning'):
                        display = f"{display} — {status}"
                    # Ensure uniqueness of label
                    if display in project_lookup:
                        display = f"{display} · {proj.get('id', '')[:6]}"
                    project_lookup[display] = {
                        'id': proj.get('id'),
                        'name': proj.get('name') or name,
                    }
                    project_values.append(display)
                project_combo = ttk.Combobox(
                    project_row,
                    textvariable=project_var,
                    values=project_values,
                    state='readonly'
                )
                project_combo.grid(row=0, column=0, sticky=tk.EW)
            else:
                project_combo = ttk.Combobox(
                    project_row,
                    textvariable=project_var,
                    values=project_values,
                    state='readonly'
                )
                project_combo.grid(row=0, column=0, sticky=tk.EW)
                project_combo.configure(state='disabled')
            project_hint = ttk.Label(
                project_row,
                text="Link to an active Living Project (optional)"
            )
            project_hint.grid(row=1, column=0, sticky=tk.W, pady=(2, 0))
            # Title
            ttk.Label(frm, text='Title', style='CategoryPanel.TLabel').grid(row=4, column=0, sticky=tk.W)
            tvar = tk.StringVar()
            ttk.Entry(frm, textvariable=tvar).grid(row=4, column=1, sticky=tk.EW)
            # Details
            ttk.Label(frm, text='Details', style='CategoryPanel.TLabel').grid(row=5, column=0, sticky=tk.NW)
            txt = scrolledtext.ScrolledText(frm, height=10, wrap=tk.WORD, font=('Arial', 9), bg='#1e1e1e', fg='#dcdcdc')
            txt.grid(row=5, column=1, sticky=tk.NSEW)
            frm.columnconfigure(1, weight=1)
            frm.rowconfigure(5, weight=1)
            # Buttons
            def do_create():
                try:
                    title_text = (tvar.get() or '').strip()
                    if not title_text:
                        messagebox.showwarning('Missing Title', 'Please enter a title.', parent=dlg); return
                    plan_name = plan_context.get('name') if isinstance(plan_context, dict) else None
                    # Auto-label in title if linked to a plan
                    if plan_name and not title_text.lower().startswith(f"plan:{plan_name.lower()}"):
                        title_text = f"Plan:{plan_name} | {title_text}"
                    selected_lp = None
                    if lp_manager and project_var.get() not in ('', '[None]'):
                        selected_lp = project_lookup.get(project_var.get())
                    selected_role_key = agent_role_lookup.get(agent_role_create_var.get(), 'general')
                    role_list = [] if selected_role_key == 'general' else [selected_role_key]
                    created = create_todo_file(
                        cat_var.get(),
                        title_text,
                        pr_local.get(),
                        txt.get('1.0', tk.END).strip(),
                        plan=plan_name,
                        living_project=selected_lp,
                        agent_roles=role_list
                    )
                    if lp_manager and selected_lp and selected_lp.get('id'):
                        try:
                            lp_manager.link_todo(selected_lp['id'], str(created))
                            log_message(f"SETTINGS: Linked todo to Living Project {selected_lp['name']} ({selected_lp['id']})")
                        except Exception as exc:
                            log_message(f"SETTINGS: Failed to link todo to Living Project: {exc}")
                    _refresh_after_plan_change()
                    try:
                        import subprocess, platform
                        system = platform.system(); path = str(created)
                        if system == 'Linux': subprocess.Popen(['xdg-open', path])
                        elif system == 'Darwin': subprocess.Popen(['open', path])
                        elif system == 'Windows': subprocess.Popen(['explorer', path])
                    except Exception: pass
                    dlg.destroy()
                except Exception as e:
                    log_message(f'SETTINGS: Error creating todo (dialog): {e}')
                    messagebox.showerror('Error', f'Failed to create todo: {e}', parent=dlg)
            btns2 = ttk.Frame(frm); btns2.grid(row=6, column=1, sticky=tk.E)
            ttk.Button(btns2, text='🤖 Ask AI', command=lambda: self._ask_ai_for_todo(
                tvar, txt, cat_var, project_var, dlg
            )).pack(side=tk.LEFT, padx=4)
            ttk.Button(btns2, text='Create', style='Action.TButton', command=do_create).pack(side=tk.LEFT, padx=4)
            ttk.Button(btns2, text='Cancel', style='Select.TButton', command=dlg.destroy).pack(side=tk.LEFT, padx=4)

        if auto_open_create:
            try:
                self.root.after(150, create_cb)
            except Exception:
                create_cb()

        def mark_cb():
            """Move todo file to completed directory."""
            sel = get_sel_from_pop()
            if not sel:
                messagebox.showinfo("No Selection", "Please select a todo to mark complete.", parent=top)
                return
            category, filename = sel
            if category == 'plans':
                _handle_plan_mark_complete(filename)
                return
            if category not in ('tasks', 'bugs', 'work_orders', 'notes', 'tests'):
                messagebox.showinfo("Invalid Selection", "Select a todo item to mark complete.", parent=top)
                return
            if not messagebox.askyesno("Mark Complete", "Mark this todo as complete?", parent=top):
                return
            try:
                # Move file to completed directory
                todo_dir = TODOS_DIR / category
                filepath = todo_dir / filename

                try:
                    todo_data = read_todo_file(filepath)
                except Exception:
                    todo_data = {}
                linked_plan_keys = self._extract_linked_plan_keys(todo_data)

                if filepath.exists():
                    move_todo_to_completed(filepath)

                _refresh_after_plan_change()
                # Clear details after marking complete
                try:
                    pr_var.set('low')
                    title_var.set('')
                    details_txt.delete('1.0', tk.END)
                except Exception:
                    pass

                for linked_plan_key in linked_plan_keys:
                    self._maybe_auto_complete_plan(linked_plan_key, parent=top, refresh_cb=_refresh_after_plan_change)
            except Exception as e:
                log_message(f"SETTINGS: Error in mark_cb: {e}")
                messagebox.showerror("Error", f"Failed to mark complete: {e}", parent=top)

        def edit_cb():
            """Open selected todo file in system editor."""
            sel = get_sel_from_pop()
            if not sel:
                messagebox.showinfo("No Selection", "Please select a todo to edit.", parent=top)
                return
            category, filename = sel
            if category not in ('tasks', 'bugs', 'work_orders', 'notes', 'completed'):
                messagebox.showinfo("Invalid Selection", "Select a valid todo to open.", parent=top)
                return
            try:
                from pathlib import Path
                todo_dir = TODOS_DIR / category
                filepath = todo_dir / filename
                if not filepath.exists():
                    messagebox.showerror("Error", "Todo file not found.", parent=top)
                    return
                import subprocess, platform
                system = platform.system()
                path = str(filepath)
                if system == 'Linux': subprocess.Popen(['xdg-open', path])
                elif system == 'Darwin': subprocess.Popen(['open', path])
                elif system == 'Windows': subprocess.Popen(['explorer', path])
            except Exception as e:
                log_message(f"SETTINGS: Error opening todo externally: {e}")
                messagebox.showerror("Error", f"Failed to open: {e}", parent=top)

        def _send_to_trash(path_str: str) -> bool:
            try:
                # Prefer send2trash if available
                try:
                    from send2trash import send2trash
                    send2trash(path_str)
                    return True
                except Exception:
                    pass
                import platform, subprocess, os, shutil
                system = platform.system()
                if system == 'Linux' and shutil.which('gio'):
                    subprocess.check_call(['gio', 'trash', path_str])
                    return True
                # Fallback: move to local app trash
                tdir = DATA_DIR / '.trash'
                tdir.mkdir(parents=True, exist_ok=True)
                import shutil as _sh
                _sh.move(path_str, tdir / Path(path_str).name)
                return True
            except Exception:
                return False

        def delete_cb():
            """Move todo file to system trash (recoverable)."""
            sel = get_sel_from_pop()
            if not sel:
                messagebox.showinfo("No Selection", "Please select a todo to delete.", parent=top)
                return
            category, filename = sel
            # Allow deleting from all categories including completed
            if category not in ('tasks', 'bugs', 'work_orders', 'notes', 'completed', 'plans', 'tests'):
                messagebox.showinfo("Invalid Selection", "Select an item to delete.", parent=top)
                return
            if not messagebox.askyesno("Confirm Delete", "Delete selected todo?", parent=top):
                return
            try:
                from pathlib import Path
                todo_dir = TODOS_DIR / category
                filepath = todo_dir / filename
                if filepath.exists():
                    _send_to_trash(str(filepath))

                self.refresh_todo_view()
                refresh_pop()
                # Clear details after delete
                try:
                    pr_var.set('low')
                    title_var.set('')
                    details_txt.delete('1.0', tk.END)
                except Exception:
                    pass
            except Exception as e:
                log_message(f"SETTINGS: Error in delete_cb: {e}")
                messagebox.showerror("Error", f"Failed to delete: {e}", parent=top)

        def save_cb():
            """Update todo file with changes from detail fields."""
            sel = get_sel_from_pop()
            if not sel:
                messagebox.showinfo("No Selection", "Please select a todo to save.", parent=top)
                return
            category, filename = sel
            if category == 'completed':
                messagebox.showinfo("Read Only", "Completed items are read-only. Delete or recreate to change.", parent=top)
                return
            try:
                # Get field values
                new_title = (title_var.get() or '').strip()
                new_priority = pr_var.get()
                new_details = details_txt.get('1.0', tk.END).strip()
                selection_label = assigned_agent_var.get()
                agent_entry = assigned_agent_lookup.get(selection_label)
                assigned_agent_name = None
                assigned_agent_role = None
                if agent_entry and agent_entry is not None and not agent_entry.get('_unavailable'):
                    assigned_agent_name = agent_entry.get('name')
                    assigned_agent_role = (agent_entry.get('role') or 'general').strip().lower()
                new_agent_roles = [] if not assigned_agent_role or assigned_agent_role == 'general' else [assigned_agent_role]

                if not new_title:
                    messagebox.showwarning("Missing Title", "Title cannot be empty.", parent=top)
                    return

                # Update file (may rename if title changed)
                from pathlib import Path
                todo_dir = TODOS_DIR / category
                filepath = todo_dir / filename
                if not filepath.exists():
                    messagebox.showerror("Error", "Todo file not found.", parent=top)
                    return

                new_filepath = update_todo_file(
                    filepath,
                    new_title,
                    new_priority,
                    new_details,
                    agent_roles=new_agent_roles,
                    assigned_agent=assigned_agent_name,
                    assigned_agent_role=assigned_agent_role,
                )

                self.refresh_todo_view()
                refresh_pop()

                # Re-select the updated item (may have new filename if title changed)
                try:
                    new_filename = new_filepath.name
                    pop_tree.selection_set(f"{category}:{new_filename}")
                except Exception:
                    pass

                populate_details_from_sel()
            except Exception as e:
                log_message(f"SETTINGS: Error in save_cb: {e}")
                messagebox.showerror("Error", f"Failed to save: {e}", parent=top)

        # Display buttons in the correct row based on whether dock is visible
        button_row = 5 if dock_visible else 5  # Buttons are always in row 5 of their container
        for i in range(5):
            btns.columnconfigure(i, weight=1)
        ttk.Button(btns, text="➕ Create Todo", command=create_cb, style='Action.TButton').grid(row=button_row, column=0, padx=3, sticky=tk.EW)
        ttk.Button(btns, text="✔ Mark Complete", command=mark_cb, style='Select.TButton').grid(row=button_row, column=1, padx=3, sticky=tk.EW)
        ttk.Button(btns, text="📄 Open File", command=edit_cb, style='Select.TButton').grid(row=button_row, column=2, padx=3, sticky=tk.EW)
        ttk.Button(btns, text="🗑 Delete Todo", command=delete_cb, style='Select.TButton').grid(row=button_row, column=3, padx=3, sticky=tk.EW)
        ttk.Button(btns, text="💾 Save (Title/Priority)", command=save_cb, style='Action.TButton').grid(row=button_row, column=4, padx=3, sticky=tk.EW)


    def show_project_todo_popup(self, project_name):
        """Show project-specific todo popup - completely separate from main todos."""
        if not project_name:
            messagebox.showerror("No Project", "Please select a project first.")
            return

        agent_role_choices = ['general', 'coder', 'debugger', 'researcher', 'planner']
        agent_role_display = {role: role.title() for role in agent_role_choices}
        agent_role_lookup = {display: role for role, display in agent_role_display.items()}

        # Ensure project todos directory exists
        get_project_todos_dir(project_name)

        top = tk.Toplevel(self.root)
        top.title(f"Project ToDo List - {project_name}")
        try:
            geom = (self.settings or {}).get('todo_geometry_project')
            if isinstance(geom, str) and 'x' in geom:
                top.geometry(geom)
            else:
                top.geometry('820x560')
        except Exception:
            top.geometry('820x560')
        try:
            top.transient(self.root)
            top.lift()
            top.attributes('-topmost', True)
            self.root.after(500, lambda: top.attributes('-topmost', False))
            top.focus_force()
        except Exception:
            pass

        # Track active state
        try:
            self.todo_popup_active = True
            self._active_todo_popup_window = top  # Phase Sub-Zero-D: Track window for dock refresh
            def _on_close():
                # PHASE SUB-ZERO-D: Stop planner log refresh
                try:
                    self._stop_planner_log_refresh()
                except Exception:
                    pass

                # Persist project geometry silently
                try:
                    w = max(400, int(top.winfo_width()))
                    h = max(300, int(top.winfo_height()))
                    self.settings['todo_geometry_project'] = f"{w}x{h}"
                    all_settings = {}
                    if self.settings_file.exists():
                        try:
                            with open(self.settings_file, 'r') as f:
                                all_settings = json.load(f)
                        except Exception:
                            all_settings = {}
                    all_settings['todo_geometry_project'] = self.settings['todo_geometry_project']
                    with open(self.settings_file, 'w') as f:
                        json.dump(all_settings, f, indent=2)
                except Exception:
                    pass
                try:
                    self.todo_popup_active = False
                except Exception:
                    pass
                try:
                    # Clear active popup reference
                    self._active_todo_popup_window = None
                except Exception:
                    pass
                try:
                    top.destroy()
                except Exception:
                    pass
            top.protocol('WM_DELETE_WINDOW', _on_close)
        except Exception:
            pass

        frame = ttk.Frame(top)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=0)
        frame.rowconfigure(3, weight=1)

        # Toggle header: Project/Main buttons
        def _open_main_from_project():
            try:
                top.destroy()
            except Exception:
                pass
            try:
                self.show_todo_popup(project_name=project_name, prefer_project=False)
            except Exception:
                pass

        log_message("TODO POPUP: Building header toggle row (Project)...")
        toggle = ttk.Frame(frame)
        toggle.grid(row=0, column=0, columnspan=2, sticky=tk.EW)
        try:
            for c in range(3):
                toggle.columnconfigure(c, weight=1)
            # [+Plan] button opens legacy manual plan creation dialog
            plan_btn = ttk.Button(toggle, text='＋ Plan', style='Action.TButton', command=lambda: self._open_plan_template_dialog(project_name))
            plan_btn.grid(row=0, column=0, sticky=tk.W, padx=(0,8))
            proj_btn = ttk.Button(toggle, text='Project ToDo List', style='Action.TButton')
            proj_btn.grid(row=0, column=1, sticky=tk.EW, padx=(0,4))
            main_btn = ttk.Button(toggle, text='Main ToDo List', style='Select.TButton', command=_open_main_from_project)
            main_btn.grid(row=0, column=2, sticky=tk.EW, padx=(4,0))
        except Exception as e:
            log_message(f"TODO POPUP: Header build error (Project): {e}")

        # Project-specific header variables
        proj_counts_var = tk.StringVar(value="Tasks: 0 | Bugs: 0 | Work-Orders: 0 | Notes: 0 | Completed: 0")
        proj_priority_var = tk.StringVar(value="Priority: High 0 | Medium 0 | Low 0")

        # Two-line header
        ttk.Label(frame, textvariable=proj_counts_var, font=("Arial", 11, "bold"), style='CategoryPanel.TLabel', anchor='center').grid(row=1, column=0, sticky=tk.EW)
        ttk.Label(frame, textvariable=proj_priority_var, font=("Arial", 10), style='CategoryPanel.TLabel', anchor='center').grid(row=2, column=0, sticky=tk.EW, pady=(0,6))

        # Top right: Trash and Folder buttons
        def open_system_trash():
            try:
                import platform, subprocess, os, shutil
                system = platform.system()
                if system == 'Linux':
                    if shutil.which('gio'):
                        subprocess.Popen(['gio', 'open', 'trash:///'])
                    elif shutil.which('xdg-open'):
                        subprocess.Popen(['xdg-open', os.path.expanduser('~/.local/share/Trash/files')])
                elif system == 'Darwin':
                    subprocess.Popen(['open', os.path.expanduser('~/.Trash')])
                elif system == 'Windows':
                    subprocess.Popen(['explorer', 'shell:RecycleBinFolder'])
            except Exception:
                pass

        try:
            trash_btn = ttk.Button(frame, text='🗑', width=3, command=open_system_trash)
            trash_btn.grid(row=0, column=1, sticky=tk.NE, padx=(6,0))
        except Exception:
            pass

        # Folder button - opens project todos folder
        def open_project_todos_folder():
            try:
                import subprocess, platform
                todos_path = str(get_project_todos_dir(project_name))
                log_message(f"SETTINGS: Opening project todos folder: {todos_path}")
                system = platform.system()
                if system == 'Linux':
                    subprocess.Popen(['xdg-open', todos_path])
                elif system == 'Darwin':
                    subprocess.Popen(['open', todos_path])
                elif system == 'Windows':
                    subprocess.Popen(['explorer', todos_path])
                else:
                    messagebox.showinfo("Unsupported OS", f"Please manually navigate to:\n{todos_path}", parent=top)
            except Exception as e:
                log_message(f"SETTINGS: Error opening project todos folder: {e}")
                messagebox.showerror("Error", f"Failed to open folder:\n{e}", parent=top)

        folder_btn = ttk.Button(frame, text="📁", command=open_project_todos_folder, width=3)
        folder_btn.grid(row=1, column=1, rowspan=2, sticky=tk.NE, padx=(6,0))

        # Tree
        log_message("TODO POPUP: Building body (tree) (Project)...")
        try:
            sub = ttk.Frame(frame)
            sub.grid(row=3, column=0, columnspan=2, sticky=tk.NSEW)
            sub.columnconfigure(0, weight=1)
            sub.rowconfigure(0, weight=1)
            scr = ttk.Scrollbar(sub, orient=tk.VERTICAL)
            scr.pack(side=tk.RIGHT, fill=tk.Y)
            pop_tree = ttk.Treeview(sub, columns=("done",), show='tree headings')
            pop_tree.heading('#0', text='Item')
            pop_tree.heading('done', text='Done')
            pop_tree.column('done', width=60, anchor=tk.CENTER, stretch=False)
            pop_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            pop_tree.configure(yscrollcommand=scr.set)
            scr.config(command=pop_tree.yview)
        except Exception as e:
            log_message(f"TODO POPUP: Tree build error (Project): {e}")
            try:
                ttk.Label(frame, text='[Tree build failed]', style='CategoryPanel.TLabel').grid(row=3, column=0, sticky=tk.W)
            except Exception:
                pass

        # Tag colors
        try:
            pop_tree.tag_configure('prio_high', foreground='#ff5555')
            pop_tree.tag_configure('prio_med', foreground='#ff9900')
            pop_tree.tag_configure('prio_low', foreground='#ffd700')
            pop_tree.tag_configure('completed', foreground='#33cc33', font=('Arial', 9, 'italic'))
        except Exception:
            pass

        # Details viewer (read-only)
        log_message("TODO POPUP: Building body (details) (Project)...")
        try:
            details = ttk.Frame(frame)
            details.grid(row=4, column=0, columnspan=2, sticky=tk.NSEW)
            frame.rowconfigure(3, weight=1)
            frame.rowconfigure(4, weight=1)
            details.columnconfigure(1, weight=1)
        except Exception as e:
            log_message(f"TODO POPUP: Details frame error (Project): {e}")
        ttk.Label(details, text='Priority', style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W)
        pr_var = tk.StringVar(value='low')
        pr_btns = ttk.Frame(details)
        pr_btns.grid(row=0, column=1, sticky=tk.W, pady=(0,6))
        ttk.Radiobutton(pr_btns, text='High', value='high', variable=pr_var).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(pr_btns, text='Medium', value='medium', variable=pr_var).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(pr_btns, text='Low', value='low', variable=pr_var).pack(side=tk.LEFT, padx=2)
        ttk.Label(details, text='Title', style='CategoryPanel.TLabel').grid(row=1, column=0, sticky=tk.W)
        title_var = tk.StringVar(value='')
        title_entry = ttk.Entry(details, textvariable=title_var)
        title_entry.grid(row=1, column=1, sticky=tk.EW, pady=(0,6))
        ttk.Label(details, text='Assigned Agent', style='CategoryPanel.TLabel').grid(row=2, column=0, sticky=tk.W)
        project_assign_row = ttk.Frame(details)
        project_assign_row.grid(row=2, column=1, sticky=tk.EW, pady=(0,2))
        project_assign_row.columnconfigure(0, weight=1)
        project_assigned_var = tk.StringVar(value='[Unassigned]')
        project_assigned_combo = ttk.Combobox(project_assign_row, textvariable=project_assigned_var, state='readonly')
        project_assigned_combo.grid(row=0, column=0, sticky=tk.EW)
        project_assign_btn = ttk.Button(project_assign_row, text='Assign Task', style='Action.TButton')
        project_assign_btn.grid(row=0, column=1, padx=(6, 0))
        project_assign_btn.state(['disabled'])
        project_assigned_lookup: dict[str, Optional[dict]] = {}

        project_assign_status_var = tk.StringVar(value='Select an agent to assign this task.')
        project_assign_status = ttk.Label(
            details,
            textvariable=project_assign_status_var,
            style='CategoryPanel.TLabel',
            wraplength=360,
            justify=tk.LEFT
        )
        project_assign_status.grid(row=3, column=1, sticky=tk.W, pady=(0,6))

        def _update_project_assigned_status() -> None:
            label = project_assigned_var.get()
            entry = project_assigned_lookup.get(label)
            if entry and entry is not None and not entry.get('_unavailable'):
                role = (entry.get('role') or 'general').title()
                project_assign_status_var.set(f"Assigned to {entry['name']} ({role})")
                project_assign_btn.state(['!disabled'])
            else:
                if label == '[No agents configured]':
                    project_assign_status_var.set('No agents configured in the Agents tab yet; add one to enable assignments.')
                elif label == '[Unassigned]':
                    project_assign_status_var.set('Select an agent and click Assign Task to dispatch this todo.')
                else:
                    project_assign_status_var.set('Previously assigned agent is no longer configured; choose another agent to reassign.')
                project_assign_btn.state(['disabled'])

        def _refresh_project_assigned_options(preferred_name: Optional[str] = None, preferred_role: Optional[str] = None) -> None:
            project_assigned_lookup.clear()
            agents = self._collect_assignable_agents()
            options: list[str] = []
            has_agents = bool(agents)
            if has_agents:
                project_assigned_lookup['[Unassigned]'] = None
                options.append('[Unassigned]')
                for entry in agents:
                    name = entry.get('name')
                    if not name:
                        continue
                    role = (entry.get('role') or 'general').strip().lower()
                    label = f"{name} ({role.title()})"
                    project_assigned_lookup[label] = {'name': name, 'role': role}
                    options.append(label)
            target_label = '[Unassigned]' if has_agents else '[No agents configured]'
            if preferred_name:
                match_label = None
                for label, entry in project_assigned_lookup.items():
                    if entry and entry.get('name') == preferred_name:
                        match_label = label
                        break
                if match_label:
                    target_label = match_label
                else:
                    role_display = (preferred_role or 'general').title()
                    unavailable_label = f"{preferred_name} ({role_display}) [Unavailable]"
                    project_assigned_lookup[unavailable_label] = {
                        'name': preferred_name,
                        'role': (preferred_role or 'general').lower(),
                        '_unavailable': True,
                    }
                    if has_agents:
                        options.append(unavailable_label)
                    else:
                        options = [unavailable_label]
                    target_label = unavailable_label

            if has_agents:
                project_assigned_combo['values'] = options
                project_assigned_combo.state(['!disabled'])
            else:
                project_assigned_combo['values'] = ('[No agents configured]',)
                project_assigned_combo.state(['disabled'])
                project_assigned_lookup['[No agents configured]'] = None
            project_assigned_var.set(target_label)
            _update_project_assigned_status()

        def _assign_project_todo_to_agent():
            sel = get_sel_from_pop()
            if not sel:
                messagebox.showinfo("Select Todo", "Select a todo before assigning it to an agent.", parent=top)
                return
            category, filename = sel
            if category == 'completed':
                messagebox.showinfo("Completed Todo", "Completed todos cannot be assigned.", parent=top)
                return
            entry = project_assigned_lookup.get(project_assigned_var.get())
            if not entry or entry is None or entry.get('_unavailable'):
                messagebox.showinfo("No Agent", "Please select a configured agent before assigning.", parent=top)
                return
            agent_name = entry.get('name')
            if not agent_name:
                messagebox.showinfo("No Agent", "Please select a configured agent before assigning.", parent=top)
                return
            record = self._build_assignment_record(category, filename, project_name)
            if not record:
                messagebox.showerror("Missing Todo", "Unable to load the selected todo file.", parent=top)
                return
            if self._assign_todo_via_agents_dock(record, agent_name):
                refresh_pop()
                populate_details_from_sel()

        project_assign_btn.configure(command=_assign_project_todo_to_agent)
        project_assigned_combo.bind('<<ComboboxSelected>>', lambda _e: _update_project_assigned_status())
        _refresh_project_assigned_options()

        ttk.Label(details, text='Linked Plans', style='CategoryPanel.TLabel').grid(row=6, column=0, sticky=tk.NW)
        project_plan_links_var = tk.StringVar(value='Linked Plans: None')
        ttk.Label(
            details,
            textvariable=project_plan_links_var,
            style='CategoryPanel.TLabel',
            wraplength=360,
            justify=tk.LEFT
        ).grid(row=6, column=1, sticky=tk.W, pady=(0,6))
        ttk.Label(details, text='Details (read-only preview)', style='CategoryPanel.TLabel').grid(row=7, column=0, sticky=tk.W)
        details_txt = scrolledtext.ScrolledText(details, height=8, wrap=tk.WORD, font=('Arial', 9), bg='#1e1e1e', fg='#dcdcdc')
        details_txt.grid(row=7, column=1, sticky=tk.NSEW)
        details.rowconfigure(7, weight=1)
        try:
            details_txt.configure(state='disabled')
        except Exception:
            pass

        # Quick Start instructions
        try:
            details_txt.configure(state='normal')
            details_txt.insert(tk.END, f"📝 Project: {project_name}\n\n")
            details_txt.insert(tk.END, "1. To CREATE: Enter Title and set Priority, click 'Create Todo', then edit the file in your editor (auto-opens).\n\n")
            details_txt.insert(tk.END, "2. To EDIT: Double-click an item or use 'Open File' to edit externally.\n\n")
            details_txt.insert(tk.END, "3. To UPDATE Title/Priority: Change fields above and click 'Save (Title/Priority)'.\n\n")
            details_txt.insert(tk.END, "This panel shows a read-only preview of the selected todo.")
            details_txt.configure(state='disabled')
            log_message(f"SETTINGS: Project todo popup opened for: {project_name}")
        except Exception as e:
            log_message(f"SETTINGS: Error adding Quick Start instructions: {e}")

        # Helper: set details preview safely in read-only widget
        def _set_details_text(text: str):
            try:
                details_txt.configure(state='normal')
                details_txt.delete('1.0', tk.END)
                details_txt.insert(tk.END, text or '')
                details_txt.configure(state='disabled')
            except Exception:
                pass

        # Populate from project-specific files
        def refresh_pop():
            log_message(f"SETTINGS: Refreshing project todos for: {project_name}")
            # Check if popup window and tree still exist
            try:
                if not pop_tree.winfo_exists():
                    log_message("SETTINGS: Project popup tree no longer exists, skipping refresh")
                    return
            except Exception:
                log_message("SETTINGS: Project popup tree widget destroyed, skipping refresh")
                return

            try:
                for i in pop_tree.get_children():
                    pop_tree.delete(i)
                log_message("SETTINGS: Project tree cleared successfully")
            except Exception as e:
                log_message(f"SETTINGS: Error clearing project popup tree: {e}")
                return
            try:
                troot = pop_tree.insert('', 'end', text='🗒 Tasks', open=True)
                broot = pop_tree.insert('', 'end', text='🐞 Bugs', open=True)
                wroot = pop_tree.insert('', 'end', text='📋 Work-Orders', open=True)
                nroot = pop_tree.insert('', 'end', text='📝 Notes', open=True)
                croot = pop_tree.insert('', 'end', text='✅ Completed', open=True)
                log_message("SETTINGS: Project tree roots created successfully")
            except Exception as e:
                log_message(f"SETTINGS: Error creating project popup tree roots: {e}")
                return

            def _prio_key(todo_dict):
                p = (todo_dict or {}).get('priority','low').lower()
                return {'high':0, 'medium':1, 'low':2}.get(p, 2)

            tcount = bcount = wcount = ncount = ccount = 0
            ph = pm = pl = 0

            # Load project-specific todos
            try:
                task_files = list_project_todo_files(project_name, 'tasks')
                log_message(f"SETTINGS: Found {len(task_files)} project task files")
                tasks_data = [read_todo_file(f) for f in task_files]
                for todo in sorted(tasks_data, key=_prio_key):
                    pr = (todo.get('priority','low') or 'low').lower()
                    tag = ('prio_high',) if pr=='high' else (('prio_med',) if pr=='medium' else ('prio_low',))
                    display_text = self._format_todo_display_text(todo, 'tasks')
                    pop_tree.insert(troot, 'end', iid=f'tasks:{todo["filename"]}', text=display_text, values=('☐',), tags=tag)
                    tcount += 1
                    if pr == 'high': ph += 1
                    elif pr == 'medium': pm += 1
                    else: pl += 1
                log_message(f"SETTINGS: Populated {len(tasks_data)} project tasks")
            except Exception as e:
                log_message(f"SETTINGS: Error populating project tasks in popup: {e}")

            try:
                bug_files = list_project_todo_files(project_name, 'bugs')
                bugs_data = [read_todo_file(f) for f in bug_files]
                for todo in sorted(bugs_data, key=_prio_key):
                    pr = (todo.get('priority','low') or 'low').lower()
                    tag = ('prio_high',) if pr=='high' else (('prio_med',) if pr=='medium' else ('prio_low',))
                    display_text = self._format_todo_display_text(todo, 'bugs')
                    pop_tree.insert(broot, 'end', iid=f'bugs:{todo["filename"]}', text=display_text, values=('☐',), tags=tag)
                    bcount += 1
                    if pr == 'high': ph += 1
                    elif pr == 'medium': pm += 1
                    else: pl += 1
            except Exception as e:
                log_message(f"SETTINGS: Error populating project bugs in popup: {e}")

            try:
                wo_files = list_project_todo_files(project_name, 'work_orders')
                wo_data = [read_todo_file(f) for f in wo_files]
                for todo in sorted(wo_data, key=_prio_key):
                    pr = (todo.get('priority','low') or 'low').lower()
                    tag = ('prio_high',) if pr=='high' else (('prio_med',) if pr=='medium' else ('prio_low',))
                    display_text = self._format_todo_display_text(todo, 'work_orders')
                    pop_tree.insert(wroot, 'end', iid=f'work_orders:{todo["filename"]}', text=display_text, values=('☐',), tags=tag)
                    wcount += 1
                    if pr == 'high': ph += 1
                    elif pr == 'medium': pm += 1
                    else: pl += 1
            except Exception as e:
                log_message(f"SETTINGS: Error populating project work-orders in popup: {e}")

            try:
                notes_files = list_project_todo_files(project_name, 'notes')
                notes_data = [read_todo_file(f) for f in notes_files]
                for todo in sorted(notes_data, key=_prio_key):
                    pr = (todo.get('priority','low') or 'low').lower()
                    tag = ('prio_high',) if pr=='high' else (('prio_med',) if pr=='medium' else ('prio_low',))
                    display_text = self._format_todo_display_text(todo, 'notes')
                    pop_tree.insert(nroot, 'end', iid=f'notes:{todo["filename"]}', text=display_text, values=('☐',), tags=tag)
                    ncount += 1
                    if pr == 'high': ph += 1
                    elif pr == 'medium': pm += 1
                    else: pl += 1
            except Exception as e:
                log_message(f"SETTINGS: Error populating project notes in popup: {e}")

            try:
                completed_files = list_project_todo_files(project_name, 'completed')
                completed_data = [read_todo_file(f) for f in completed_files]
                for todo in completed_data:
                    display_text = self._format_todo_display_text(todo, 'completed')
                    pop_tree.insert(croot, 'end', iid=f'completed:{todo["filename"]}', text=display_text, values=('☑',), tags=('completed',))
                    ccount += 1
            except Exception as e:
                log_message(f"SETTINGS: Error populating project completed in popup: {e}")

            # Update counts
            proj_counts_var.set(f"Tasks: {tcount} | Bugs: {bcount} | Work-Orders: {wcount} | Notes: {ncount} | Completed: {ccount}")
            proj_priority_var.set(f"Priority: High {ph} | Medium {pm} | Low {pl}")

        refresh_pop()

        def _refresh_project_after_change():
            previous_selection = get_sel_from_pop()
            try:
                refresh_pop()
            except Exception:
                pass
            try:
                self.refresh_todo_view()
            except Exception:
                pass
            if previous_selection:
                try:
                    pop_tree.selection_set(f"{previous_selection[0]}:{previous_selection[1]}")
                except Exception:
                    pass
            try:
                populate_details_from_sel()
            except Exception:
                pass
            try:
                populate_details_from_sel()
            except Exception:
                pass

        # Buttons and callbacks
        btns = ttk.Frame(frame)
        btns.grid(row=5, column=0, columnspan=2, sticky=tk.EW, pady=(6,0))
        for i in range(5):
            btns.columnconfigure(i, weight=1)

        def get_sel_from_pop():
            sel = pop_tree.selection()
            if not sel:
                return None
            item = sel[0]
            if ':' not in item:
                return None
            category, filename = item.split(':', 1)
            return category, filename

        def populate_details_from_sel():
            log_message("SETTINGS: Project populate_details_from_sel() called")
            sel = get_sel_from_pop()
            if not sel:
                log_message("SETTINGS: No selection, keeping Quick Start instructions")
                return
            try:
                pr_var.set('low')
                title_var.set('')
                _set_details_text('')
                project_plan_links_var.set('Linked Plans: None')
                log_message(f"SETTINGS: Project fields cleared for selection: {sel}")
            except Exception:
                pass
            _refresh_project_assigned_options()
            category, filename = sel
            if category == 'completed':
                try:
                    title_var.set('[Completed - Read Only]')
                    _set_details_text('Completed items are read-only. Delete to remove or recreate as new todo.')
                    project_plan_links_var.set('Linked Plans: None')
                except Exception:
                    pass
                return

            assigned_name = None
            assigned_role = None
            try:
                from pathlib import Path
                todos_dir = get_project_todos_dir(project_name)
                todo_dir = todos_dir / category
                filepath = todo_dir / filename
                if not filepath.exists():
                    return
                todo_data = read_todo_file(filepath)
                pr_var.set(todo_data.get('priority', 'low'))
                title_var.set(todo_data.get('title', ''))
                assigned_name = (todo_data.get('assigned_agent') or '').strip() or None
                assigned_role = (todo_data.get('assigned_agent_role') or '').strip().lower() or None
                linked_plan_keys = self._extract_linked_plan_keys(todo_data)
                if category == 'plans':
                    plan_key = (todo_data.get('linked_plan') or '').strip()
                    if not plan_key:
                        plan_key = self._normalize_plan_key(todo_data.get('title'))
                    project_plan_links_var.set(f"Plan Key: {plan_key or 'None'}")
                    preview = self._build_plan_preview_text(plan_key) if plan_key else "No plan key detected."
                    _set_details_text(f"{todo_data.get('details', '')}\n\nLinked Todos:\n{preview}")
                else:
                    if linked_plan_keys:
                        project_plan_links_var.set(f"Linked Plans: {', '.join(linked_plan_keys)}")
                    else:
                        project_plan_links_var.set("Linked Plans: None")
                    _set_details_text(todo_data.get('details', ''))
            except Exception as e:
                log_message(f"SETTINGS: Error loading project todo file: {e}")
                assigned_name = None
                assigned_role = None

            _refresh_project_assigned_options(assigned_name, assigned_role)

        try:
            pop_tree.bind('<<TreeviewSelect>>', lambda e: populate_details_from_sel())
        except Exception:
            pass
        try:
            populate_details_from_sel()
        except Exception:
            pass

        def create_cb():
            """Open full create dialog for a new project todo."""
            dlg = tk.Toplevel(top)
            dlg.title('Create Project ToDo')
            dlg.geometry('640x420')
            try:
                dlg.transient(top); dlg.grab_set()
            except Exception:
                pass
            frm = ttk.Frame(dlg, padding=10)
            frm.pack(fill=tk.BOTH, expand=True)
            # Category
            ttk.Label(frm, text='Category', style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W)
            cat_var = tk.StringVar(value='tasks')
            cats = [('Tasks','tasks'),('Bugs','bugs'),('Work-Orders','work_orders'),('Notes','notes')]
            cat_row = ttk.Frame(frm); cat_row.grid(row=0, column=1, sticky=tk.W)
            for label, val in cats:
                ttk.Radiobutton(cat_row, text=label, value=val, variable=cat_var).pack(side=tk.LEFT, padx=4)
            # Priority
            ttk.Label(frm, text='Priority', style='CategoryPanel.TLabel').grid(row=1, column=0, sticky=tk.W)
            pr_local = tk.StringVar(value='low')
            pr_row = ttk.Frame(frm); pr_row.grid(row=1, column=1, sticky=tk.W)
            ttk.Radiobutton(pr_row, text='High', value='high', variable=pr_local).pack(side=tk.LEFT, padx=4)
            ttk.Radiobutton(pr_row, text='Medium', value='medium', variable=pr_local).pack(side=tk.LEFT, padx=4)
            ttk.Radiobutton(pr_row, text='Low', value='low', variable=pr_local).pack(side=tk.LEFT, padx=4)
            # Agent role
            project_agent_role_var = tk.StringVar(value=agent_role_display['general'])
            ttk.Label(frm, text='Agent Type', style='CategoryPanel.TLabel').grid(row=2, column=0, sticky=tk.W)
            project_agent_role_combo = ttk.Combobox(
                frm,
                textvariable=project_agent_role_var,
                values=list(agent_role_display.values()),
                state='readonly'
            )
            project_agent_role_combo.grid(row=2, column=1, sticky=tk.W, pady=(0,2))
            project_agent_role_status_var = tk.StringVar(value=self._get_agent_role_assignment_summary('general')[0])
            project_agent_role_status = ttk.Label(
                frm,
                textvariable=project_agent_role_status_var,
                style='CategoryPanel.TLabel',
                wraplength=360,
                justify=tk.LEFT
            )
            project_agent_role_status.grid(row=3, column=1, sticky=tk.W, pady=(0,8))

            def _update_project_create_role_status():
                role_key = agent_role_lookup.get(project_agent_role_var.get(), 'general')
                summary, level = self._get_agent_role_assignment_summary(role_key)
                project_agent_role_status_var.set(summary)
                color = "#ffcc66" if level == 'warning' else "#8de0ff"
                try:
                    project_agent_role_status.configure(foreground=color)
                except Exception:
                    pass
            _update_project_create_role_status()
            project_agent_role_combo.bind('<<ComboboxSelected>>', lambda e: _update_project_create_role_status())
            # Title
            ttk.Label(frm, text='Title', style='CategoryPanel.TLabel').grid(row=4, column=0, sticky=tk.W)
            tvar = tk.StringVar()
            ttk.Entry(frm, textvariable=tvar).grid(row=4, column=1, sticky=tk.EW)
            # Details
            ttk.Label(frm, text='Details', style='CategoryPanel.TLabel').grid(row=5, column=0, sticky=tk.NW)
            txt = scrolledtext.ScrolledText(frm, height=10, wrap=tk.WORD, font=('Arial', 9), bg='#1e1e1e', fg='#dcdcdc')
            txt.grid(row=5, column=1, sticky=tk.NSEW)
            frm.columnconfigure(1, weight=1)
            frm.rowconfigure(5, weight=1)
            # Buttons
            def do_create():
                try:
                    title_text = (tvar.get() or '').strip()
                    if not title_text:
                        messagebox.showwarning('Missing Title', 'Please enter a title.', parent=dlg); return
                    plan_name = plan_context.get('name') if isinstance(plan_context, dict) else None
                    if plan_name and not title_text.lower().startswith(f"plan:{plan_name.lower()}"):
                        title_text = f"Plan:{plan_name} | {title_text}"
                    selected_role_key = agent_role_lookup.get(project_agent_role_var.get(), 'general')
                    role_list = [] if selected_role_key == 'general' else [selected_role_key]
                    created = create_project_todo_file(
                        project_name,
                        cat_var.get(),
                        title_text,
                        pr_local.get(),
                        txt.get('1.0', tk.END).strip(),
                        plan=plan_name,
                        agent_roles=role_list
                    )
                    self._link_todo_to_living_project(project_name, created)
                    refresh_pop()
                    try:
                        import subprocess, platform
                        system = platform.system(); path = str(created)
                        if system == 'Linux': subprocess.Popen(['xdg-open', path])
                        elif system == 'Darwin': subprocess.Popen(['open', path])
                        elif system == 'Windows': subprocess.Popen(['explorer', path])
                    except Exception: pass
                    dlg.destroy()
                except Exception as e:
                    log_message(f'SETTINGS: Error creating project todo (dialog): {e}')
                    messagebox.showerror('Error', f'Failed to create todo: {e}', parent=dlg)
            btns2 = ttk.Frame(frm); btns2.grid(row=5, column=1, sticky=tk.E)
            ttk.Button(btns2, text='Create', style='Action.TButton', command=do_create).pack(side=tk.LEFT, padx=4)
            ttk.Button(btns2, text='Cancel', style='Select.TButton', command=dlg.destroy).pack(side=tk.LEFT, padx=4)

        def mark_cb():
            sel = get_sel_from_pop()
            if not sel:
                messagebox.showinfo("No Selection", "Please select a todo to mark complete.", parent=top)
                return
            category, filename = sel
            if category not in ('tasks', 'bugs', 'work_orders', 'notes'):
                messagebox.showinfo("Invalid Selection", "Select a task, bug, work-order, or note to mark complete.", parent=top)
                return
            if not messagebox.askyesno("Mark Complete", "Mark this todo as complete?", parent=top):
                return
            try:
                todos_dir = get_project_todos_dir(project_name)
                todo_dir = todos_dir / category
                filepath = todo_dir / filename
                if not filepath.exists():
                    messagebox.showerror("Error", "Todo file not found.", parent=top)
                    return
                try:
                    todo_data = read_todo_file(filepath)
                except Exception:
                    todo_data = {}
                linked_plan_keys = self._extract_linked_plan_keys(todo_data)
                move_project_todo_to_completed(project_name, filepath)
                _refresh_project_after_change()
                try:
                    pr_var.set('low')
                    title_var.set('')
                    _set_details_text('')
                except Exception:
                    pass
                for linked_plan_key in linked_plan_keys:
                    self._maybe_auto_complete_plan(linked_plan_key, parent=top, refresh_cb=_refresh_project_after_change)
            except Exception as e:
                log_message(f"SETTINGS: Error in project mark_cb: {e}")
                messagebox.showerror("Error", f"Failed to mark complete: {e}", parent=top)

        def save_cb():
            sel = get_sel_from_pop()
            if not sel:
                messagebox.showinfo("No Selection", "Please select a todo to save.", parent=top)
                return
            category, filename = sel
            if category == 'completed':
                messagebox.showinfo("Read Only", "Completed items are read-only. Delete or recreate to change.", parent=top)
                return
            try:
                new_title = (title_var.get() or '').strip()
                new_priority = pr_var.get()
                new_details = details_txt.get('1.0', tk.END).strip()
                selection_label = project_assigned_var.get()
                agent_entry = project_assigned_lookup.get(selection_label)
                assigned_agent_name = None
                assigned_agent_role = None
                if agent_entry and agent_entry is not None and not agent_entry.get('_unavailable'):
                    assigned_agent_name = agent_entry.get('name')
                    assigned_agent_role = (agent_entry.get('role') or 'general').strip().lower()
                new_agent_roles = [] if not assigned_agent_role or assigned_agent_role == 'general' else [assigned_agent_role]
                if not new_title:
                    messagebox.showwarning("Missing Title", "Title cannot be empty.", parent=top)
                    return
                from pathlib import Path
                todos_dir = get_project_todos_dir(project_name)
                todo_dir = todos_dir / category
                filepath = todo_dir / filename
                if not filepath.exists():
                    messagebox.showerror("Error", "Todo file not found.", parent=top)
                    return
                new_filepath = update_todo_file(
                    filepath,
                    new_title,
                    new_priority,
                    new_details,
                    agent_roles=new_agent_roles,
                    assigned_agent=assigned_agent_name,
                    assigned_agent_role=assigned_agent_role,
                )
                refresh_pop()
                try:
                    new_filename = new_filepath.name
                    pop_tree.selection_set(f"{category}:{new_filename}")
                except Exception:
                    pass
                populate_details_from_sel()
            except Exception as e:
                log_message(f"SETTINGS: Error in project save_cb: {e}")
                messagebox.showerror("Error", f"Failed to save: {e}", parent=top)

        def _send_to_trash(path_str: str) -> bool:
            try:
                try:
                    from send2trash import send2trash
                    send2trash(path_str)
                    return True
                except Exception:
                    pass
                import platform, subprocess, os, shutil
                system = platform.system()
                if system == 'Linux' and shutil.which('gio'):
                    subprocess.check_call(['gio', 'trash', path_str])
                    return True
                tdir = get_project_todos_dir(project_name).parent / '.trash'
                tdir.mkdir(parents=True, exist_ok=True)
                import shutil as _sh
                _sh.move(path_str, tdir / Path(path_str).name)
                return True
            except Exception:
                return False

        def delete_cb():
            sel = get_sel_from_pop()
            if not sel:
                messagebox.showinfo("No Selection", "Please select a todo to delete.", parent=top)
                return
            category, filename = sel
            if category not in ('tasks', 'bugs', 'work_orders', 'notes', 'completed'):
                messagebox.showinfo("Invalid Selection", "Select an item to delete.", parent=top)
                return
            if not messagebox.askyesno("Confirm Delete", "Delete selected todo?", parent=top):
                return
            try:
                from pathlib import Path
                todos_dir = get_project_todos_dir(project_name)
                todo_dir = todos_dir / category
                filepath = todo_dir / filename
                if filepath.exists():
                    _send_to_trash(str(filepath))
                refresh_pop()
                try:
                    pr_var.set('low')
                    title_var.set('')
                    details_txt.delete('1.0', tk.END)
                except Exception:
                    pass
            except Exception as e:
                log_message(f"SETTINGS: Error in project delete_cb: {e}")
                messagebox.showerror("Error", f"Failed to delete: {e}", parent=top)

        def edit_cb():
            sel = get_sel_from_pop()
            if not sel:
                messagebox.showinfo("No Selection", "Please select a todo to edit.", parent=top)
                return
            category, filename = sel
            if category not in ('tasks', 'bugs', 'work_orders', 'notes', 'completed', 'plans', 'tests'):
                messagebox.showinfo("Invalid Selection", "Select a valid todo to open.", parent=top)
                return

            try:
                from pathlib import Path
                todos_dir = get_project_todos_dir(project_name)
                todo_dir = todos_dir / category
                filepath = todo_dir / filename
                if not filepath.exists():
                    messagebox.showerror("Error", "Todo file not found.", parent=top)
                    return
                import subprocess, platform
                system = platform.system()
                path = str(filepath)
                if system == 'Linux': subprocess.Popen(['xdg-open', path])
                elif system == 'Darwin': subprocess.Popen(['open', path])
                elif system == 'Windows': subprocess.Popen(['explorer', path])
            except Exception as e:
                log_message(f"SETTINGS: Error opening project todo externally: {e}")
                messagebox.showerror("Error", f"Failed to open: {e}", parent=top)

        # Action buttons (includes Open)
        for i in range(5):
            try:
                btns.columnconfigure(i, weight=1)
            except Exception:
                pass
        ttk.Button(btns, text="➕ Create Todo", command=create_cb, style='Action.TButton').grid(row=0, column=0, padx=3, sticky=tk.EW)
        ttk.Button(btns, text="✔ Mark Complete", command=mark_cb, style='Select.TButton').grid(row=0, column=1, padx=3, sticky=tk.EW)
        ttk.Button(btns, text="📄 Open File", command=edit_cb, style='Select.TButton').grid(row=0, column=2, padx=3, sticky=tk.EW)
        ttk.Button(btns, text="🗑 Delete Todo", command=delete_cb, style='Select.TButton').grid(row=0, column=3, padx=3, sticky=tk.EW)
        ttk.Button(btns, text="💾 Save (Title/Priority)", command=save_cb, style='Action.TButton').grid(row=0, column=4, padx=3, sticky=tk.EW)

        def _project_link_plan_cb():
            sel = get_sel_from_pop()
            if not sel:
                messagebox.showinfo("Select Todo", "Select a todo before linking to a plan.", parent=top)
                return
            category, filename = sel
            if category in ('plans', 'completed'):
                messagebox.showinfo("Unsupported", "Linking is only available for active todos.", parent=top)
                return
            todo_info = self._resolve_todo_info(category, filename, project_name)
            if not todo_info:
                messagebox.showerror("Missing File", "Unable to locate the selected todo file.", parent=top)
                return
            self._open_link_todo_to_plan_dialog(
                top,
                todo_info,
                _refresh_project_after_change,
                preferred_project=project_name
            )

        def _project_merge_plans_cb():
            self._open_merge_plans_dialog(top, _refresh_project_after_change)

        project_link_row = ttk.Frame(frame)
        project_link_row.grid(row=6, column=0, columnspan=2, sticky=tk.EW, pady=(4, 0))
        frame.rowconfigure(6, weight=0)
        project_link_row.columnconfigure(0, weight=1)
        project_link_row.columnconfigure(1, weight=1)
        ttk.Button(
            project_link_row,
            text="🔗 Link to Plan",
            style='Action.TButton',
            command=_project_link_plan_cb
        ).grid(row=0, column=0, sticky=tk.EW, padx=(0, 4))
        ttk.Button(
            project_link_row,
            text="🔀 Merge Plans",
            style='Select.TButton',
            command=_project_merge_plans_cb
        ).grid(row=0, column=1, sticky=tk.EW, padx=(4, 0))

        # Double-click to open file
        try:
            pop_tree.bind('<Double-1>', lambda e: edit_cb())
        except Exception:
            pass

    def todo_create(self):
        """Legacy entry point now redirects to the file-backed popup dialog."""
        self.show_todo_popup(auto_open_create=True)

    def todo_mark_complete(self):
        """Move selected todo file to completed directory."""
        sel = self._get_selected_todo()
        if not sel:
            messagebox.showinfo("No Selection", "Please select a todo (task/bug) to mark complete.")
            return
        category, filename = sel
        if category not in ('tasks', 'bugs', 'work_orders', 'notes'):
            messagebox.showinfo("Invalid Selection", "Select a task or bug, not a category header.")
            return
        if not messagebox.askyesno("Mark Complete", "Mark this todo as complete?"):
            return
        try:
            from pathlib import Path
            todo_dir = TODOS_DIR / category
            filepath = todo_dir / filename
            if filepath.exists():
                move_todo_to_completed(filepath)
            self.refresh_todo_view()
        except Exception as e:
            log_message(f"SETTINGS: Error marking complete: {e}")
            messagebox.showerror("Error", f"Failed to mark complete: {e}")

    def todo_edit(self):
        """Open edit dialog for selected todo file."""
        sel = self._get_selected_todo()
        if not sel:
            messagebox.showinfo("No Selection", "Please select a todo to edit.")
            return
        category, filename = sel
        if category not in ('tasks', 'bugs', 'work_orders', 'notes'):
            messagebox.showinfo("Invalid Selection", "Select a task or bug to edit.")
            return
        try:
            from pathlib import Path
            todo_dir = TODOS_DIR / category
            filepath = todo_dir / filename
            if not filepath.exists():
                messagebox.showerror("Error", "Todo file not found.")
                return

            # Load todo from file
            todo_data = read_todo_file(filepath)

            # Edit popup with priority + title + details
            top = tk.Toplevel(self.root)
            top.title('Edit ToDo')
            frm = ttk.Frame(top, padding=8)
            frm.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frm, text='Priority', style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W)
            pr = tk.StringVar(value=todo_data.get('priority', 'low'))

            def setp(v):
                pr.set(v)

            btnf = ttk.Frame(frm)
            btnf.grid(row=0, column=1, sticky=tk.W)
            ttk.Button(btnf, text='High', style='Action.TButton', command=lambda: setp('high')).pack(side=tk.LEFT, padx=2)
            ttk.Button(btnf, text='Medium', style='Action.TButton', command=lambda: setp('medium')).pack(side=tk.LEFT, padx=2)
            ttk.Button(btnf, text='Low', style='Action.TButton', command=lambda: setp('low')).pack(side=tk.LEFT, padx=2)

            ttk.Label(frm, text='Title', style='CategoryPanel.TLabel').grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
            title_var = tk.StringVar(value=todo_data.get('title', ''))
            ent = ttk.Entry(frm, textvariable=title_var, width=50)
            ent.grid(row=1, column=1, sticky=tk.EW, pady=(6, 0))

            ttk.Label(frm, text='Details', style='CategoryPanel.TLabel').grid(row=2, column=0, sticky=tk.W, pady=(6, 0))
            txt = scrolledtext.ScrolledText(frm, height=10, wrap=tk.WORD, font=('Arial', 9), bg='#1e1e1e', fg='#dcdcdc')
            txt.grid(row=2, column=1, sticky=tk.NSEW, pady=(6, 0))
            frm.columnconfigure(1, weight=1)
            frm.rowconfigure(2, weight=1)
            txt.insert(tk.END, todo_data.get('details', ''))

            def save_edits():
                try:
                    new_title = (title_var.get() or '').strip()
                    new_priority = pr.get()
                    new_details = txt.get('1.0', tk.END).strip()

                    if not new_title:
                        messagebox.showwarning("Missing Title", "Title cannot be empty.", parent=top)
                        return

                    # Update file (may rename if title changed)
                    update_todo_file(filepath, new_title, new_priority, new_details)

                    self.refresh_todo_view()
                    top.destroy()
                except Exception as e:
                    log_message(f"SETTINGS: Error saving edits: {e}")
                    messagebox.showerror("Error", f"Failed to save: {e}", parent=top)

            ttk.Button(frm, text='Save', style='Action.TButton', command=save_edits).grid(row=3, column=1, sticky=tk.E, pady=6)
        except Exception as e:
            log_message(f"SETTINGS: Error in todo_edit: {e}")
            messagebox.showerror("Error", f"Failed to open editor: {e}")

    def todo_delete(self):
        """Delete selected todo file."""
        sel = self._get_selected_todo()
        if not sel:
            messagebox.showinfo("No Selection", "Please select a todo to delete.")
            return
        category, filename = sel
        # Allow deleting from all categories including completed
        if category not in ('tasks', 'bugs', 'work_orders', 'notes', 'completed'):
            messagebox.showinfo("Invalid Selection", "Select an item to delete.")
            return
        if not messagebox.askyesno("Confirm Delete", "Delete selected todo?"):
            return
        try:
            from pathlib import Path
            todo_dir = TODOS_DIR / category
            filepath = todo_dir / filename
            if filepath.exists():
                delete_todo_file(filepath)
            self.refresh_todo_view()
        except Exception as e:
            log_message(f"SETTINGS: Error deleting todo: {e}")
            messagebox.showerror("Error", f"Failed to delete: {e}")

    def get_setting(self, key, default=None):
        """Get a setting value"""
        return self.settings.get(key, default)

    def create_resource_settings(self, parent):
        """Create resource limiting settings"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # Scrollable frame
        canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        content_frame = ttk.Frame(canvas)

        content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        # CPU Settings
        cpu_section = ttk.LabelFrame(content_frame, text="💻 CPU Limits", style='TLabelframe')
        cpu_section.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(cpu_section, text="Max CPU Threads:", style='Config.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.max_cpu_threads = tk.IntVar(value=self.settings.get('max_cpu_threads', 2))
        ttk.Spinbox(
            cpu_section,
            from_=1,
            to=32,
            textvariable=self.max_cpu_threads,
            width=10
        ).grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(
            cpu_section,
            text="Lower values prevent system freezing during training",
            font=("Arial", 8),
            foreground='#888888'
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 10))

        # Memory Settings
        mem_section = ttk.LabelFrame(content_frame, text="🧠 Memory Limits", style='TLabelframe')
        mem_section.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(mem_section, text="Max RAM Usage (%):", style='Config.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.max_ram_percent = tk.IntVar(value=self.settings.get('max_ram_percent', 70))
        ttk.Spinbox(
            mem_section,
            from_=50,
            to=95,
            increment=5,
            textvariable=self.max_ram_percent,
            width=10
        ).grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(
            mem_section,
            text="Recommended: 70% for 8GB RAM, 80% for 16GB+",
            font=("Arial", 8),
            foreground='#888888'
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 10))

        # Training Memory Settings
        train_mem_section = ttk.LabelFrame(content_frame, text="⚙️ Training Memory", style='TLabelframe')
        train_mem_section.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(train_mem_section, text="Max Sequence Length:", style='Config.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.max_seq_length = tk.IntVar(value=self.settings.get('max_seq_length', 256))
        seq_lengths = [128, 256, 512, 1024, 2048]
        seq_combo = ttk.Combobox(
            train_mem_section,
            textvariable=self.max_seq_length,
            values=seq_lengths,
            state="readonly",
            width=10
        )
        seq_combo.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(train_mem_section, text="Gradient Accumulation:", style='Config.TLabel').grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=5
        )
        self.gradient_accumulation = tk.IntVar(value=self.settings.get('gradient_accumulation', 16))
        ttk.Spinbox(
            train_mem_section,
            from_=1,
            to=32,
            textvariable=self.gradient_accumulation,
            width=10
        ).grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)

        ttk.Label(
            train_mem_section,
            text="8GB RAM: Use 256 seq length + 16 accumulation\n16GB RAM: Use 512 seq length + 8 accumulation",
            font=("Arial", 8),
            foreground='#888888',
            justify=tk.LEFT
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 10))

        # Warning section
        warning_section = ttk.LabelFrame(content_frame, text="⚠️ Important Notes", style='TLabelframe')
        warning_section.pack(fill=tk.X, padx=10, pady=10)

        warning_text = """• Lower values = slower training but safer for your system
• If training crashes with OOM error, reduce sequence length
• If system freezes, reduce CPU threads
• These are DEFAULT values - you can override in Runner panel
• Changes take effect on next training session"""

        ttk.Label(
            warning_section,
            text=warning_text,
            font=("Arial", 9),
            foreground='#ffaa00',
            justify=tk.LEFT
        ).pack(padx=10, pady=10, anchor=tk.W)

    def _populate_tab_visibility_controls(self, parent_frame):
        """Populates the 'Tab Visibility' section with checkboxes for each tab."""
        # Clear existing controls
        for widget in parent_frame.winfo_children():
            widget.destroy()

        # Get a list of all known tabs (main tabs)
        known_tabs = [
            ("Training Tab", "training_tab_enabled"),
            ("Models Tab", "models_tab_enabled"),
            ("Settings Tab", "settings_tab_enabled"),
            ("Custom Code Tab", "custom_code_tab_enabled"),
        ]

        for display_name, setting_key in known_tabs:
            var = tk.BooleanVar(value=self.settings.get(setting_key, True)) # Default to enabled
            self.tab_enabled_vars[setting_key] = var

            cb = ttk.Checkbutton(
                parent_frame,
                text=f"Show {display_name}",
                variable=var,
                command=self._on_tab_visibility_changed,
                style='Category.TCheckbutton'
            )
            cb.pack(fill=tk.X, padx=10, pady=2, anchor=tk.W)

        # --- Tab Reordering Mode ---
        reorder_frame = ttk.LabelFrame(parent_frame, text="Tab Reordering Mode", style='TLabelframe')
        reorder_frame.pack(fill=tk.X, padx=10, pady=10)

        modes = [
            ("D&D", "dnd"),
            ("Arrow Buttons", "arrow")
        ]

        for text, mode in modes:
            rb = ttk.Radiobutton(
                reorder_frame,
                text=text,
                variable=self.reorder_mode,
                value=mode,
                command=self._on_reorder_mode_changed,
                style='Category.TRadiobutton' # You might need to define this style
            )
            rb.pack(fill=tk.X, padx=10, pady=2, anchor=tk.W)

        # Save button to persist the current tab order
        ttk.Button(
            reorder_frame,
            text="💾 Save Tab Order",
            command=self.save_tab_order_now,
            style='Action.TButton'
        ).pack(fill=tk.X, padx=10, pady=(8, 4))

    def save_tab_order_now(self):
        """Capture current notebook tab order and persist to settings.json."""
        if not self.main_gui or not hasattr(self.main_gui, 'notebook') or not self.tab_instances:
            messagebox.showerror("Error", "Cannot save tab order. Internal components not found.")
            return

        notebook = self.main_gui.notebook
        # Build order from current notebook tabs
        new_tab_order = []
        for tab_id in notebook.tabs():
            for name, info in self.tab_instances.items():
                if str(info['frame']) == tab_id:
                    new_tab_order.append(name)
                    break

        if not new_tab_order:
            messagebox.showerror("Error", "Could not determine current tab order.")
            return

        # Also capture per-tab panel orders (headers)
        panel_orders = {}
        for tab_name, meta in self.tab_instances.items():
            nb = None
            inst = meta.get('instance')
            for attr in (
                'training_notebook',   # TrainingTab
                'sub_notebook',        # CustomCodeTab
                'settings_notebook',   # SettingsTab
                'model_info_notebook', # ModelsTab
                'models_notebook'      # Fallback
            ):
                nb = getattr(inst, attr, None) if inst is not None else None
                if nb is not None:
                    break
            if nb is None:
                continue
            headers = []
            try:
                for tid in nb.tabs():
                    try:
                        headers.append(nb.tab(tid, 'text'))
                    except Exception:
                        pass
            except Exception:
                pass
            if headers:
                panel_orders[tab_name] = headers

        # Update in-memory settings and persist
        self.settings['tab_order'] = new_tab_order
        if panel_orders:
            self.settings['panel_orders'] = panel_orders
        try:
            self.save_settings_to_file()
            messagebox.showinfo("Tab Order Saved", "Tab order saved. Use Quick Restart to apply.")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save tab order: {e}")

    def _on_tab_visibility_changed(self):
        """Callback when a tab visibility checkbox is toggled."""
        # Immediately save settings to persist the change
        self.save_settings_to_file()
        messagebox.showinfo("Tab Visibility Changed", "Tab visibility settings saved. Please Quick Restart the application to apply changes.")

    def _on_reorder_mode_changed(self):
        """Callback when the reorder mode is changed."""
        mode = self.reorder_mode.get()
        
        if mode == 'arrow':
            if hasattr(self, 'move_left_button'):
                self.move_left_button.pack(fill=tk.X, pady=2)
                self.move_right_button.pack(fill=tk.X, pady=2)
        else:
            if hasattr(self, 'move_left_button'):
                self.move_left_button.pack_forget()
                self.move_right_button.pack_forget()

        # Only show guidance when not programmatically toggled
        if not getattr(self, '_suppress_reorder_popup', False):
            if mode in ('arrow', 'dnd'):
                messagebox.showinfo(
                    "Reorder Mode",
                    f"Reorder mode set to '{mode}'.\n\nChanges are temporary until you click 'Save Tab Order'."
                )

    def move_tab(self, direction):
        """Move the selected tab left or right in the order, dynamically."""
        log_message(f"SETTINGS: move_tab called with direction: {direction}")
        if not self.selected_tree_item:
            log_message("SETTINGS: move_tab aborted - nothing selected.")
            messagebox.showwarning("No Selection", "Please select a tab or panel from the tree to move.")
            return

        if self.selected_tree_item.get('type') == 'panel_header':
            # Delegate to panel move within the tab's notebook
            return self._move_panel_within_tab(direction)

        if self.selected_tree_item.get('type') != 'tab':
            log_message("SETTINGS: move_tab aborted - selection is not a main tab.")
            messagebox.showwarning("Wrong Selection", "Select a main tab header to reorder tabs.")
            return

        selected_tab_dir_name = self.selected_tree_item.get('tab_name') or self.selected_tree_item['path'].name
        log_message(f"SETTINGS: Selected tab for move: {selected_tab_dir_name}")

        if not self.main_gui or not hasattr(self.main_gui, 'notebook') or not self.tab_instances:
            log_message("SETTINGS ERROR: Main GUI, notebook, or tab_instances not available.")
            messagebox.showerror("Error", "Cannot reorder tabs. Internal components not found.")
            return

        notebook = self.main_gui.notebook

        if selected_tab_dir_name not in self.tab_instances:
            log_message(f"SETTINGS ERROR: Selected tab '{selected_tab_dir_name}' not in tab_instances.")
            messagebox.showerror("Error", "Selected tab not found in the application's tab registry.")
            return
            
        tab_to_move_frame = self.tab_instances[selected_tab_dir_name]['frame']

        try:
            current_index = notebook.index(tab_to_move_frame)
        except tk.TclError:
            log_message(f"SETTINGS ERROR: Could not find tab '{selected_tab_dir_name}' in the notebook.")
            messagebox.showerror("Error", "Could not find the selected tab in the notebook.")
            return

        new_index = current_index
        if direction == "left":
            if current_index > 0:
                new_index = current_index - 1
            else:
                log_message("SETTINGS: Cannot move tab further left.")
                return
        elif direction == "right":
            if current_index < len(notebook.tabs()) - 1:
                new_index = current_index + 1
            else:
                log_message("SETTINGS: Cannot move tab further right.")
                return
        
        log_message(f"SETTINGS: Moving tab from index {current_index} to {new_index}.")
        
        # Move the tab in the notebook
        notebook.insert(new_index, tab_to_move_frame)

        # Update the tab_order in settings dictionary (without saving to file)
        new_tab_order = []
        for tab_id in notebook.tabs():
            for name, info in self.tab_instances.items():
                if str(info['frame']) == tab_id:
                    new_tab_order.append(name)
                    break
        
        self.settings['tab_order'] = new_tab_order
        log_message(f"SETTINGS: New tab order in memory: {new_tab_order}")

        # Refresh the tree to show the new order based on the in-memory settings
        self.refresh_tabs_tree()

    def _move_panel_within_tab(self, direction):
        """Move selected panel header left/right inside its parent tab's notebook."""
        try:
            tab_name = self.selected_tree_item.get('tab_name')
            header = self.selected_tree_item.get('panel_header')
            if not tab_name or not header:
                raise ValueError("Missing tab/panel selection")

            if not self.tab_instances or tab_name not in self.tab_instances:
                messagebox.showerror("Error", "Cannot reorder panels. Tab instance not found.")
                return

            instance = self.tab_instances[tab_name]['instance']
            notebook = None
            for attr in (
                'training_notebook',
                'sub_notebook',
                'settings_notebook',
                'model_info_notebook',
                'models_notebook'
            ):
                nb = getattr(instance, attr, None)
                if nb is not None:
                    notebook = nb
                    break
            if notebook is None:
                messagebox.showerror("Error", "Selected tab has no panels to reorder.")
                return

            tab_ids = notebook.tabs()
            current_index = None
            for idx, tid in enumerate(tab_ids):
                try:
                    if notebook.tab(tid, 'text') == header:
                        current_index = idx
                        break
                except Exception:
                    continue
            if current_index is None:
                messagebox.showerror("Error", "Could not locate selected panel in the tab.")
                return

            new_index = current_index
            if direction == 'left':
                if current_index > 0:
                    new_index = current_index - 1
                else:
                    return
            elif direction == 'right':
                if current_index < len(tab_ids) - 1:
                    new_index = current_index + 1
                else:
                    return

            tab_id = tab_ids[current_index]
            notebook.insert(new_index, tab_id)

            # Refresh the tree to reflect the new order
            self.refresh_tabs_tree()
        except Exception as e:
            log_message(f"SETTINGS ERROR: Panel move failed: {e}")
            messagebox.showerror("Error", f"Failed to reorder panel: {e}")

    def refresh_settings_tab(self):
        """Refresh the settings tab - reloads settings from file."""
        # Reload settings from file
        self.settings = self.load_settings()

        # Update all variable values from reloaded settings
        if hasattr(self, 'max_cpu_threads'):
            self.max_cpu_threads.set(self.settings.get('max_cpu_threads', 2))
        if hasattr(self, 'max_ram_percent'):
            self.max_ram_percent.set(self.settings.get('max_ram_percent', 70))
        if hasattr(self, 'max_seq_length'):
            self.max_seq_length.set(self.settings.get('max_seq_length', 256))
        if hasattr(self, 'gradient_accumulation'):
            self.gradient_accumulation.set(self.settings.get('gradient_accumulation', 16))

        log_message("SETTINGS: Settings tab refreshed.")

    def quick_restart_application(self):
        try:
            log_message("SETTINGS: User initiated Quick Restart. (Method entered)")
            # Call save_settings_to_file directly. It handles its own success/error messages.
            self.save_settings_to_file()
                
            # --- RESTART LOGIC ---
            try:
                main_script_path = DATA_DIR / "interactive_trainer_gui_NEW.py"
                if not main_script_path.exists():
                    main_script_path = Path(sys.argv[0])
    
                python_executable = sys.executable
                
                log_message(f"SETTINGS:   - Executable: {python_executable}")
                log_message(f"SETTINGS:   - Script: {main_script_path}")
    
                # Replace the current process with a new one
                os.execl(python_executable, python_executable, str(main_script_path))
    
            except Exception as e:
                messagebox.showerror("Restart Failed", f"Could not restart the application: {e}")
                log_message(f"SETTINGS ERROR: Restart failed: {e}")

        except Exception as e:
            log_message(f"SETTINGS CRITICAL ERROR: Unhandled exception in quick_restart_application: {e}")
            import traceback
            log_message(f"SETTINGS CRITICAL TRACEBACK: {traceback.format_exc()}")
            messagebox.showerror("Critical Error", f"An unexpected error occurred during Quick Restart: {e}\nCheck debug log for details.")

    def copy_log_to_clipboard(self):
        """Copies the content of the currently displayed log to the clipboard."""
        try:
            log_content = self.debug_output.get(1.0, tk.END)
            if not log_content.strip():
                messagebox.showinfo("Clipboard", "Log is empty. Nothing to copy.")
                return

            self.root.clipboard_clear()
            self.root.clipboard_append(log_content)
            messagebox.showinfo("Clipboard", "Log content copied to clipboard!")
            log_message("SETTINGS: Log content copied to clipboard.")
        except Exception as e:
            messagebox.showerror("Clipboard Error", f"Failed to copy log to clipboard: {e}")
            log_message(f"SETTINGS ERROR: Failed to copy log to clipboard: {e}")

    def _run_debug_probe(self, tab: str):
        """Placeholder hook for running per-tab diagnostic probes."""
        log_message(f"DEBUG_PROBE: requested for tab '{tab}' (pending implementation)")

    def ask_debugger_agent(self):
        """Open the Ask Debugger Agent dialog with the selected bug context."""
        # Phase Sub-Zero-E: Add debug logging
        try:
            from debug_logger import get_logger
            _debug_logger = get_logger("SettingsTab")
            _debug_logger.method_call("ask_debugger_agent")
        except ImportError:
            _debug_logger = None

        if not ASK_AI_DIALOG_AVAILABLE:
            messagebox.showwarning(
                "Feature Not Available",
                "The Ask Debugger Agent dialog is unavailable. Ensure dialogs/ask_ai_dialog.py is accessible."
            )
            return

        bug_entry = self._get_bug_context_for_debugger()
        if not bug_entry:
            messagebox.showinfo(
                "No Bug Context",
                "Capture or select a bug in the Debug tab before consulting the debugger agent."
            )
            return

        bug_filename = self._extract_bug_filename(bug_entry)
        if not bug_filename:
            messagebox.showerror(
                "Bug Context Missing",
                "Unable to determine the bug file for the selected entry."
            )
            return

        bug_details = get_bug_details_for_agent(bug_filename, include_context=True)
        if bug_details.get('error'):
            messagebox.showerror("Debug Agent", bug_details['error'])
            return

        event_payload = self._build_bug_event_payload(bug_entry, bug_details)
        try:
            show_ask_ai_dialog(self.root, 'orchestrator_debugger', event_payload, DATA_DIR)
            log_message("SETTINGS: Debugger agent consultation initialized")
        except Exception as exc:
            messagebox.showerror(
                "Debug Agent",
                f"Failed to open debugger agent dialog: {exc}"
            )
            log_message(f"SETTINGS ERROR: Failed to open debugger agent dialog: {exc}")

    def _get_bug_context_for_debugger(self) -> Optional[Dict[str, Any]]:
        bug_panel = getattr(self, 'bug_panel', None)
        if bug_panel:
            getter = getattr(bug_panel, 'get_selected_bug_entry', None)
            bug_entry = getter() if getter else None
            if not bug_entry and hasattr(bug_panel, 'get_latest_bug_entry'):
                bug_entry = bug_panel.get_latest_bug_entry()
            if bug_entry:
                return bug_entry

        tracker = None
        if get_bug_tracker:
            try:
                tracker = get_bug_tracker()
            except Exception as exc:
                log_message(f"SETTINGS: Unable to access bug tracker ({exc})")
        if tracker:
            try:
                recent = tracker.get_recent_session_bugs(limit=1) or tracker.get_recent_bugs(limit=1)
            except Exception as exc:
                log_message(f"SETTINGS: Failed to fetch recent bugs ({exc})")
                recent = []
            if recent:
                entry = dict(recent[0])
                if not entry.get('file') and entry.get('bug_id'):
                    bug_id = entry['bug_id']
                    filename = bug_id if str(bug_id).endswith('.json') else f"{bug_id}.json"
                    entry['file'] = str(Path(tracker.bug_dir) / filename)
                return entry
        return None

    def _extract_bug_filename(self, bug_entry: Dict[str, Any]) -> Optional[str]:
        bug_file = bug_entry.get('file')
        if bug_file:
            return Path(bug_file).name
        bug_id = bug_entry.get('bug_id') or bug_entry.get('_bug_id')
        if not bug_id:
            return None
        bug_id_str = str(bug_id)
        if not bug_id_str.startswith('BUG_'):
            bug_id_str = f"BUG_{bug_id_str}"
        if not bug_id_str.endswith('.json'):
            bug_id_str = f"{bug_id_str}.json"
        return bug_id_str

    def _build_bug_event_payload(self, bug_entry: Dict[str, Any], bug_details: Dict[str, Any]) -> Dict[str, Any]:
        change_ctx = bug_entry.get('change_context') or bug_details.get('change_context') or {}
        diff_snippet = change_ctx.get('diff_snippet')
        working_dir_hint = bug_entry.get('working_dir_hint') or change_ctx.get('working_dir_hint')
        suggested_fix = bug_details.get('suggested_fix') or bug_entry.get('suggested_fix')
        confidence = bug_details.get('confidence') or bug_entry.get('confidence')
        try:
            confidence = float(confidence) if confidence is not None else None
        except Exception:
            confidence = None

        bug_id = (
            bug_details.get('bug_id')
            or bug_entry.get('bug_id')
            or bug_entry.get('_bug_id')
            or (Path(bug_entry.get('file')).stem if bug_entry.get('file') else None)
        )
        error_type = bug_details.get('error_type', 'Bug')
        error_message = bug_details.get('error_message', '')
        message_text = (f"{error_type}: {error_message}" if error_message else error_type)

        event_data = {
            'bug_id': bug_id,
            'message': message_text,
            'error_type': error_type,
            'error_message': error_message,
            'file_path': bug_details.get('file_path'),
            'line_number': bug_details.get('line_number'),
            'stack_trace': bug_details.get('stack_trace'),
            'code_context': bug_details.get('code_context'),
            'suggested_fix': suggested_fix,
            'confidence': confidence,
            'diff_snippet': diff_snippet,
            'working_dir_hint': working_dir_hint,
            'recent_changes': bug_details.get('recent_changes'),
        }
        return {
            'event_type': 'bug_detected',
            'data': event_data,
        }

    def create_custom_code_settings(self, parent):
        """Create Custom Code feature settings"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # Scrollable frame
        canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        content_frame = ttk.Frame(canvas)

        content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        custom_settings = self.settings.get('custom_code', {})

        # Tool Orchestrator Section
        orchestrator_section = ttk.LabelFrame(content_frame, text="🎯 Tool Orchestrator", style='TLabelframe')
        orchestrator_section.pack(fill=tk.X, padx=10, pady=10)

        self.enable_tool_orchestrator = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_tool_orchestrator', False)
        )
        ttk.Checkbutton(
            orchestrator_section,
            text="Enable Advanced Tool Orchestrator",
            variable=self.enable_tool_orchestrator,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        ttk.Label(
            orchestrator_section,
            text="Enables intelligent tool chaining, confirmation gates, and risk assessment",
            font=("Arial", 8),
            foreground='#888888'
        ).pack(anchor=tk.W, padx=10, pady=(0, 10))

        # Format Translators Section
        translators_section = ttk.LabelFrame(content_frame, text="🔄 Format Translators", style='TLabelframe')
        translators_section.pack(fill=tk.X, padx=10, pady=10)

        self.enable_json_translator = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_json_translator', True)
        )
        ttk.Checkbutton(
            translators_section,
            text="JSON Format Translator",
            variable=self.enable_json_translator,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        self.enable_yaml_translator = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_yaml_translator', False)
        )
        ttk.Checkbutton(
            translators_section,
            text="YAML Format Translator",
            variable=self.enable_yaml_translator,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        # Parsers Section
        parsers_section = ttk.LabelFrame(content_frame, text="📋 Response Parsers", style='TLabelframe')
        parsers_section.pack(fill=tk.X, padx=10, pady=10)

        self.enable_structured_parser = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_structured_parser', True)
        )
        ttk.Checkbutton(
            parsers_section,
            text="Structured Output Parser",
            variable=self.enable_structured_parser,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        self.enable_datetime_parser = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_datetime_parser', False)
        )
        ttk.Checkbutton(
            parsers_section,
            text="DateTime Parser",
            variable=self.enable_datetime_parser,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        self.enable_regex_parser = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_regex_parser', False)
        )
        ttk.Checkbutton(
            parsers_section,
            text="Regex Pattern Parser",
            variable=self.enable_regex_parser,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        # Advanced Features Section
        advanced_section = ttk.LabelFrame(content_frame, text="⚙️ Advanced Features", style='TLabelframe')
        advanced_section.pack(fill=tk.X, padx=10, pady=10)

        self.enable_context_scorer = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_context_scorer', False)
        )
        ttk.Checkbutton(
            advanced_section,
            text="Context Scoring (RAG optimization)",
            variable=self.enable_context_scorer,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        self.enable_time_slicer = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_time_slicer', False)
        )
        ttk.Checkbutton(
            advanced_section,
            text="Time-Sliced Generation",
            variable=self.enable_time_slicer,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        self.enable_verification_engine = tk.BooleanVar(
            value=self.settings.get('custom_code', {}).get('enable_verification_engine', False)
        )
        ttk.Checkbutton(
            advanced_section,
            text="Verification Engine (output validation)",
            variable=self.enable_verification_engine,
            style='Category.TCheckbutton'
        ).pack(anchor=tk.W, padx=10, pady=5)

        # Vector MCP Bridge Section
        self.vector_mcp_enable_var = tk.BooleanVar(value=False)

        vector_section = ttk.LabelFrame(content_frame, text="📡 Vector MCP Bridge", style='TLabelframe')
        vector_section.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(
            vector_section,
            text="Expose the existing h-codex vector index via scripts/run_vector_mcp.py so MCP-compatible agents can search code without touching the unfinished RAG UI.",
            font=("Arial", 9),
            foreground='#bbbbbb',
            wraplength=520,
            justify=tk.LEFT
        ).pack(fill=tk.X, padx=10, pady=(5, 10))

        toggle_row = ttk.Frame(vector_section)
        toggle_row.pack(fill=tk.X, padx=10, pady=(0, 5))

        ttk.Checkbutton(
            toggle_row,
            text="Allow Vector MCP Access (On Hold)",
            variable=self.vector_mcp_enable_var,
            command=self._handle_vector_mcp_toggle,
            style='Category.TCheckbutton',
            state=tk.DISABLED
        ).pack(side=tk.LEFT)

        ttk.Label(
            toggle_row,
            textvariable=self.vector_mcp_status_var,
            font=("Arial", 9, "italic"),
            foreground='#aaaaaa'
        ).pack(side=tk.LEFT, padx=10)

        btn_row = ttk.Frame(vector_section)
        btn_row.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(
            btn_row,
            text="Health Check",
            command=self.run_vector_mcp_healthcheck,
            style='Select.TButton',
            state=tk.DISABLED
        ).pack(side=tk.LEFT, padx=(0, 6))

        ttk.Label(
            vector_section,
            text="Implementation paused: Postgres + vector services under investigation. MCP bridge will return once backend is stable.",
            font=("Arial", 8),
            foreground='#888888',
            justify=tk.LEFT
        ).pack(fill=tk.X, padx=10, pady=(0, 5))

        # Save button
        ttk.Button(
            content_frame,
            text="💾 Save Custom Code Settings",
            command=self.save_custom_code_settings,
            style='Action.TButton'
        ).pack(pady=20, padx=10, fill=tk.X)

    def save_custom_code_settings(self):
        """Save custom code settings"""
        try:
            # Read existing settings
            all_settings = {}
            if self.settings_file.exists():
                try:
                    with open(self.settings_file, 'r') as f:
                        all_settings = json.load(f)
                except Exception as e:
                    log_message(f"SETTINGS ERROR: Could not read settings: {e}")

            # Update custom_code section
            all_settings['custom_code'] = {
                'enable_tool_orchestrator': self.enable_tool_orchestrator.get(),
                'enable_json_translator': self.enable_json_translator.get(),
                'enable_yaml_translator': self.enable_yaml_translator.get(),
                'enable_structured_parser': self.enable_structured_parser.get(),
                'enable_datetime_parser': self.enable_datetime_parser.get(),
                'enable_regex_parser': self.enable_regex_parser.get(),
                'enable_context_scorer': self.enable_context_scorer.get(),
                'enable_time_slicer': self.enable_time_slicer.get(),
                'enable_verification_engine': self.enable_verification_engine.get(),
                'vector_mcp_enabled': self.vector_mcp_enable_var.get() if hasattr(self, "vector_mcp_enable_var") else False,
            }

            # Save
            with open(self.settings_file, 'w') as f:
                json.dump(all_settings, f, indent=2)

            log_message("SETTINGS: Custom Code settings saved successfully")
            messagebox.showinfo("Settings Saved", "Custom Code settings have been saved successfully!")

        except Exception as e:
            log_message(f"SETTINGS ERROR: Failed to save custom code settings: {e}")
            messagebox.showerror("Save Error", f"Failed to save settings: {e}")

    def _vector_mcp_python_executable(self) -> Optional[str]:
        if sys.executable:
            return sys.executable
        for candidate in ("python3", "python"):
            path = shutil.which(candidate)
            if path:
                return path
        return None

    def _set_vector_mcp_enabled(self, value: bool) -> None:
        if not hasattr(self, "vector_mcp_enable_var"):
            return
        self._suppress_vector_mcp_toggle = True
        try:
            self.vector_mcp_enable_var.set(value)
        finally:
            self._suppress_vector_mcp_toggle = False

    def _handle_vector_mcp_toggle(self) -> None:
        if self._suppress_vector_mcp_toggle:
            return
        enabled = self.vector_mcp_enable_var.get()
        if enabled:
            ok, message = self._execute_vector_mcp_healthcheck()
            if ok:
                self.vector_mcp_status_var.set("Ready – start MCP client")
                log_message("SETTINGS: Vector MCP access enabled; prerequisites satisfied.")
                messagebox.showinfo(
                    "Vector MCP",
                    "Healthcheck passed.\n\nFrom Codex, run:\n"
                    "  /mcp add vector-mcp python3 scripts/run_vector_mcp.py\n"
                    "(set cwd to the project root), then `/mcp connect vector-mcp`.",
                )
            else:
                summary = f"Vector MCP prerequisites failed:\n{message}"
                log_message(f"SETTINGS: {summary}")
                messagebox.showerror("Vector MCP", summary)
                self.vector_mcp_status_var.set("Failed – see Debug tab")
                self._set_vector_mcp_enabled(False)
        else:
            self.vector_mcp_status_var.set("Disabled")
            log_message("SETTINGS: Vector MCP access disabled by user.")

    def _execute_vector_mcp_healthcheck(self) -> tuple[bool, str]:
        if not VECTOR_MCP_SCRIPT.exists():
            return False, f"Helper script not found at {VECTOR_MCP_SCRIPT}"

        python_exec = self._vector_mcp_python_executable()
        if not python_exec:
            return False, "Python executable not found in PATH. Install Python 3 to continue."

        try:
            result = subprocess.run(
                [python_exec, str(VECTOR_MCP_SCRIPT), "--healthcheck"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            return False, "Healthcheck timed out. Ensure Postgres + h-codex services are reachable."
        except Exception as exc:
            return False, f"Failed to run healthcheck: {exc}"

        output = (result.stdout or "") + (result.stderr or "")
        success = result.returncode == 0
        return success, output.strip() or ("Healthcheck passed." if success else "Healthcheck failed.")

    def run_vector_mcp_healthcheck(self):
        success, message = self._execute_vector_mcp_healthcheck()
        if success:
            self.vector_mcp_status_var.set("Ready – start MCP client")
            messagebox.showinfo("Vector MCP", message)
        else:
            summary = f"Vector MCP prerequisites failed:\n{message}"
            log_message(f"SETTINGS: {summary}")
            self.vector_mcp_status_var.set("Failed – see Debug tab")
            messagebox.showerror("Vector MCP", summary)

    def create_debug_tab(self, parent):
        """Create the live debug feed tab with log history viewer."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1) # Row 0 header, 1 toggles, 2 controls, 3 log display

        # Header
        header = ttk.Frame(parent)
        header.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)
        ttk.Label(header, text="🐞 Live Debug Log", font=("Arial", 12, "bold")).pack(side=tk.LEFT)

        # Ask Debugger Agent button (right side)
        ttk.Button(
            header,
            text="🤖 Ask Debugger Agent",
            command=self.ask_debugger_agent,
            style='Accent.TButton'
        ).pack(side=tk.RIGHT, padx=5)

        # Tab filters row
        toggle_frame = ttk.Frame(parent)
        toggle_frame.grid(row=1, column=0, sticky=tk.EW, padx=10, pady=(0,5))
        toggle_frame.columnconfigure(0, weight=1)

        tab_label_map = {
            'general': 'General',
            'custom_code': 'Custom Code',
            'training': 'Training',
            'models': 'Models',
            'settings': 'Settings',
            'agents': 'Agents',
            'automation': 'Automation',
            'external': 'External',
        }
        for base_tab in tab_label_map.keys():
            set_tab_enabled(base_tab, True)
        initial_state = get_tab_state()
        ordered_tabs = list(tab_label_map.keys())
        for extra in sorted(initial_state.keys()):
            if extra not in ordered_tabs:
                ordered_tabs.append(extra)

        self.debug_tab_toggle_vars = {}
        self._pending_tab_filter_sync = []

        for tab in ordered_tabs:
            frame = ttk.Frame(toggle_frame)
            frame.pack(side=tk.LEFT, padx=6)
            var = tk.BooleanVar(value=initial_state.get(tab, True))
            self.debug_tab_toggle_vars[tab] = var

            label = tab_label_map.get(tab, tab.replace('_', ' ').title())

            def _make_toggle(t=tab, v=var):
                def _toggle():
                    set_tab_enabled(t, v.get())
                    try:
                        if hasattr(self, 'enhanced_viewer') and self.enhanced_viewer:
                            self.enhanced_viewer.set_tab_filter(t, v.get())
                    except Exception:
                        pass
                return _toggle

            toggle_cmd = _make_toggle()
            ttk.Checkbutton(frame, text=label, variable=var, command=toggle_cmd).pack(side=tk.TOP, anchor=tk.W)
            self._pending_tab_filter_sync.append(toggle_cmd)
            ttk.Button(frame, text='[Bug Probe]', style='Select.TButton', command=lambda t=tab: self._run_debug_probe(t)).pack(side=tk.TOP, pady=(2,0))

        # Log file selection controls
        controls_frame = ttk.Frame(parent)
        controls_frame.grid(row=2, column=0, sticky=tk.EW, padx=10, pady=5)
        controls_frame.columnconfigure(1, weight=1)

        ttk.Label(controls_frame, text="View Log History:", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        
        self.log_file_var = tk.StringVar()
        self.log_file_combobox = ttk.Combobox(
            controls_frame,
            textvariable=self.log_file_var,
            state="readonly",
            width=50
        )
        self.log_file_combobox.grid(row=0, column=1, sticky=tk.EW, padx=(0, 5))
        self.log_file_combobox.bind("<<ComboboxSelected>>", self.on_log_file_selected)

        ttk.Button(controls_frame, text="🔄", command=self.populate_log_file_combobox, style='Select.TButton', width=4).grid(row=0, column=2, sticky=tk.E, padx=(0, 5))
        ttk.Button(controls_frame, text="📎", command=self.copy_log_to_clipboard, style='Select.TButton', width=4).grid(row=0, column=3, sticky=tk.E)

        # Log display - PanedWindow for log + bug panel
        content_pane = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        content_pane.grid(row=3, column=0, sticky='nsew', padx=10, pady=(0, 10))

        # Left: Log viewer (70%)
        log_frame = ttk.Frame(content_pane)
        self.debug_output = scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Courier", 9),
            bg="#1e1e1e", fg="#d4d4d4", relief='flat'
        )
        self.debug_output.pack(fill=tk.BOTH, expand=True)

        # Wrap with EnhancedDebugViewer
        if ENHANCED_DEBUG_AVAILABLE:
            self.enhanced_viewer = EnhancedDebugViewer(self.debug_output)

        # Debug capture controls
        dbg_ctrls = ttk.Frame(parent)
        dbg_ctrls.grid(row=4, column=0, sticky=tk.EW, padx=10, pady=(0,6))
        self.debug_autocapture_var = tk.BooleanVar(value=True)
        if ENHANCED_DEBUG_AVAILABLE:
            cb = ttk.Checkbutton(dbg_ctrls, text='Capture bugs from live logs', variable=self.debug_autocapture_var)
            cb.pack(side=tk.LEFT)
            def _toggle_capture(*_):
                try:
                    self.enhanced_viewer.enable_bug_capture = bool(self.debug_autocapture_var.get())
                except Exception:
                    pass
            self.debug_autocapture_var.trace_add('write', lambda *_: _toggle_capture())
            if not hasattr(self, '_pending_debug_sync'):
                self._pending_debug_sync = []
            self._pending_debug_sync.append(_toggle_capture)

        # Right: Bug Summary Panel (30%)
        bug_frame = ttk.Frame(content_pane, width=320)
        if ENHANCED_DEBUG_AVAILABLE:
            self.bug_panel = BugSummaryPanel(
                bug_frame,
                session_only=bool(self.change_watcher_settings.get('bug_session_only', True)),
                settings_provider=self._load_bug_panel_settings,
                settings_saver=self._save_bug_panel_settings,
            )
            self.bug_panel.pack(fill=tk.BOTH, expand=True)
            # Initial refresh to populate bug list
            self.bug_panel.refresh()
            if self.bug_panel.auto_refresh_var.get():
                self.bug_panel.start_auto_refresh(self.bug_panel._refresh_interval_ms)

        # Change guard controls (Changes Mode + indicators)
        guard_group = ttk.LabelFrame(parent, text='Change Guard')
        guard_group.grid(row=5, column=0, sticky=tk.EW, padx=10, pady=(0, 8))
        guard_group.columnconfigure(1, weight=1)

        self.changes_mode_enabled_var = tk.BooleanVar(value=self.change_watcher_settings.get('changes_mode_enabled', False))
        changes_mode_cb = ttk.Checkbutton(
            guard_group,
            text='Changes Mode (read/write)',
            variable=self.changes_mode_enabled_var,
            command=self._on_changes_mode_toggled
        )
        changes_mode_cb.grid(row=0, column=0, sticky=tk.W, padx=4, pady=(4, 2))
        if not WATCHER_AVAILABLE:
            changes_mode_cb.state(['disabled'])

        self.changes_mode_status_var = tk.StringVar(value='Changes Allowed: Allowed')
        ttk.Label(guard_group, textvariable=self.changes_mode_status_var, style='Config.TLabel').grid(
            row=0, column=1, sticky=tk.E, padx=4, pady=(4, 2)
        )
        self._update_changes_mode_indicator()
        self._sync_gatekeeper_state()

        duplicate_btn = ttk.Button(
            guard_group,
            text='Duplicate Version',
            style='Action.TButton',
            command=self._on_duplicate_version
        )
        duplicate_btn.grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=4, pady=(0, 4))
        if not WATCHER_AVAILABLE:
            duplicate_btn.state(['disabled'])
        self.duplicate_version_button = duplicate_btn

        # Change watcher controls
        watcher_group = ttk.LabelFrame(parent, text='Watcher Service')
        watcher_group.grid(row=6, column=0, sticky=tk.EW, padx=10, pady=(0, 8))
        watcher_group.columnconfigure(1, weight=1)

        self.change_watcher_enabled_var = tk.BooleanVar(value=self.change_watcher_settings.get('enabled', False))
        enable_cb = ttk.Checkbutton(
            watcher_group,
            text='Watcher Service (background scans)',
            variable=self.change_watcher_enabled_var,
            command=self._apply_change_watcher_from_ui
        )
        enable_cb.grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=4, pady=(4,2))
        if not WATCHER_AVAILABLE:
            enable_cb.state(['disabled'])

        ttk.Label(watcher_group, text='Scan interval (s):').grid(row=1, column=0, sticky=tk.W, padx=4)
        self.change_watcher_interval_var = tk.IntVar(value=self.change_watcher_settings.get('interval_seconds', 60))
        interval_spin = tk.Spinbox(
            watcher_group,
            from_=10,
            to=3600,
            increment=10,
            width=6,
            textvariable=self.change_watcher_interval_var,
            command=self._change_watcher_interval_changed
        )
        interval_spin.grid(row=1, column=1, sticky=tk.W, pady=2)
        if not WATCHER_AVAILABLE:
            interval_spin.configure(state='disabled')

        ttk.Label(watcher_group, text='Ignore patterns (comma separated):').grid(row=2, column=0, sticky=tk.W, padx=4, pady=(4,0))
        self.change_watcher_ignore_var = tk.StringVar(value=",".join(self.change_watcher_settings.get('ignore_patterns', [])))
        ignore_entry = ttk.Entry(watcher_group, textvariable=self.change_watcher_ignore_var)
        ignore_entry.grid(row=2, column=1, sticky=tk.EW, padx=(0,4), pady=(4,0))
        if not WATCHER_AVAILABLE:
            ignore_entry.state(['disabled'])

        self.change_watcher_silent_var = tk.BooleanVar(value=self.change_watcher_settings.get('silent', True))
        silent_cb = ttk.Checkbutton(
            watcher_group,
            text='Silent mode (log only)',
            variable=self.change_watcher_silent_var,
            command=self._apply_change_watcher_from_ui
        )
        silent_cb.grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=4, pady=(4,0))
        if not WATCHER_AVAILABLE:
            silent_cb.state(['disabled'])

        button_row = ttk.Frame(watcher_group)
        button_row.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(6,0))
        ttk.Button(button_row, text='Save & Apply', style='Action.TButton', command=self._apply_change_watcher_from_ui).pack(side=tk.LEFT, padx=2)
        scan_btn = ttk.Button(button_row, text='Scan Now', command=self._change_watcher_scan_now)
        scan_btn.pack(side=tk.LEFT, padx=2)
        baseline_btn = ttk.Button(button_row, text='Rebuild Baseline', command=self._change_watcher_rebuild_baseline)
        baseline_btn.pack(side=tk.LEFT, padx=2)
        if not WATCHER_AVAILABLE:
            scan_btn.state(['disabled'])
            baseline_btn.state(['disabled'])

        self.change_watcher_status_var = tk.StringVar(value='Watcher unavailable' if not WATCHER_AVAILABLE else 'Watcher idle')
        ttk.Label(watcher_group, textvariable=self.change_watcher_status_var, style='Config.TLabel').grid(row=5, column=0, columnspan=2, sticky=tk.W, padx=4, pady=(6,4))

        # Add to paned window
        content_pane.add(log_frame, weight=3)
        content_pane.add(bug_frame, weight=1)

        if ENHANCED_DEBUG_AVAILABLE:
            for func in getattr(self, '_pending_tab_filter_sync', []):
                try:
                    func()
                except Exception:
                    pass
            for func in getattr(self, '_pending_debug_sync', []):
                try:
                    func()
                except Exception:
                    pass

        # Debug capture controls row (below the panes)
        dbg_ctrls = ttk.Frame(parent)
        dbg_ctrls.grid(row=4, column=0, sticky=tk.EW, padx=10, pady=(0,6))
        self.debug_autocapture_var = tk.BooleanVar(value=True)
        if ENHANCED_DEBUG_AVAILABLE:
            cb = ttk.Checkbutton(dbg_ctrls, text='Capture bugs from live logs', variable=self.debug_autocapture_var)
            cb.pack(side=tk.LEFT)
            def _toggle_capture(*_):
                try:
                    self.enhanced_viewer.enable_bug_capture = bool(self.debug_autocapture_var.get())
                except Exception:
                    pass
            self.debug_autocapture_var.trace_add('write', lambda *_: _toggle_capture())
            if not hasattr(self, '_pending_debug_sync'):
                self._pending_debug_sync = []
            self._pending_debug_sync.append(_toggle_capture)

            # Show session-only bugs toggle
            self.debug_session_only_var = tk.BooleanVar(value=True)
            cb2 = ttk.Checkbutton(dbg_ctrls, text='Show session-only bugs', variable=self.debug_session_only_var)
            cb2.pack(side=tk.LEFT, padx=(12,0))
            def _toggle_session(*_):
                try:
                    val = bool(self.debug_session_only_var.get())
                    log_message(f"[DEBUG_VIEW][TOGGLE] checkbox -> {val} (scheduling)")
                    # Schedule on Tk thread to avoid colliding with any active refresh
                    def _do_set(v=val):
                        try:
                            log_message("[DEBUG_VIEW][TOGGLE] calling bug_panel.set_session_only(...) now")
                            self.bug_panel.set_session_only(v)
                        except Exception as exc:
                            log_message(f"[DEBUG_VIEW][TOGGLE] set_session_only error: {exc}")
                    self.root.after(0, _do_set)
                except Exception:
                    pass
            self.debug_session_only_var.trace_add('write', lambda *_: _toggle_session())
            if not hasattr(self, '_pending_debug_sync'):
                self._pending_debug_sync = []
            self._pending_debug_sync.append(_toggle_session)

        # Populate combobox and start polling
        self.populate_log_file_combobox()
        self.start_log_polling()
        self._apply_change_watcher_from_ui(initial=True)

    def populate_log_file_combobox(self):
        """Populates the combobox with available log files, sorting them and labeling the current session's log as 'Live Log'."""
        log_dir = DATA_DIR / "DeBug"
        self.log_file_paths.clear() # Clear previous mappings

        if not log_dir.exists():
            self.log_file_combobox['values'] = []
            self.log_file_var.set("No logs found")
            return

        list_of_files = glob.glob(str(log_dir / 'debug_log_*.txt'))
        if not list_of_files:
            self.log_file_combobox['values'] = []
            self.log_file_var.set("No logs found")
            return

        list_of_files.sort(key=os.path.getctime, reverse=True)
        
        display_names = []
        current_session_log_path = logger_util.get_log_file_path() # Get the path of the current session's log

        for f_path in list_of_files:
            if str(f_path) == current_session_log_path:
                display_name = "Live Log"
            else:
                display_name = os.path.basename(f_path)
            display_names.append(display_name)
            self.log_file_paths[display_name] = str(f_path)

        self.log_file_combobox['values'] = display_names
        
        # Select 'Live Log' by default if it exists, otherwise the latest file
        if "Live Log" in display_names:
            self.log_file_var.set("Live Log")
        elif display_names:
            self.log_file_var.set(display_names[0])
        
        self.on_log_file_selected() # Load the selected log

    def on_log_file_selected(self, event=None):
        """Handles selection of a log file from the combobox, displaying its content and managing polling."""
        selected_display_name = self.log_file_var.get()
        if not selected_display_name or selected_display_name == "No logs found":
            return

        # Stop live polling initially
        self.stop_log_polling()

        selected_full_path = self.log_file_paths.get(selected_display_name)
        if not selected_full_path:
            self.debug_output.config(state=tk.NORMAL)
            self.debug_output.delete(1.0, tk.END)
            self.debug_output.insert(tk.END, f"Error: Log file path not found for: {selected_display_name}")
            self.debug_output.config(state=tk.DISABLED)
            return

        if not Path(selected_full_path).exists():
            self.debug_output.config(state=tk.NORMAL)
            self.debug_output.delete(1.0, tk.END)
            self.debug_output.insert(tk.END, f"Error: Log file not found on disk: {selected_full_path}")
            self.debug_output.config(state=tk.DISABLED)
            return

        self.current_log_file = selected_full_path
        self.last_read_position = 0

        self.debug_output.config(state=tk.NORMAL)
        self.debug_output.delete(1.0, tk.END)
        self.debug_output.insert(tk.END, f"--- Viewing log: {selected_display_name} ---\n\n")
        self.debug_output.config(state=tk.DISABLED)

        try:
            with open(self.current_log_file, 'r') as f:
                content = f.read()
                if content:
                    # Use enhanced viewer for color coding if available
                    if hasattr(self, 'enhanced_viewer') and ENHANCED_DEBUG_AVAILABLE:
                        for line in content.split('\n'):
                            self.enhanced_viewer.insert_line(line.rstrip(), auto_highlight=True)
                    else:
                        # Fallback to original
                        self.debug_output.config(state=tk.NORMAL)
                        self.debug_output.insert(tk.END, content)
                        self.debug_output.see(tk.END)
                        self.debug_output.config(state=tk.DISABLED)
                self.last_read_position = f.tell()
                # Initial load: refresh bug summary after ingest
                try:
                    if ENHANCED_DEBUG_AVAILABLE and hasattr(self, 'bug_panel') and self.bug_panel:
                        self.bug_panel.refresh()
                except Exception:
                    pass
                # After ingest, refresh summary panel to surface new bugs
                try:
                    if ENHANCED_DEBUG_AVAILABLE and hasattr(self, 'bug_panel') and self.bug_panel:
                        self.bug_panel.refresh()
                except Exception:
                    pass
        except Exception as e:
            self.debug_output.config(state=tk.NORMAL)
            self.debug_output.insert(tk.END, f"\n--- ERROR READING LOG: {e} ---\n")
            self.debug_output.config(state=tk.DISABLED)

        # If the selected file is the current session's log, restart live polling
        if self.current_log_file == logger_util.get_log_file_path():
            self.start_log_polling() # Restart polling for the live log

    # --- Evaluation Policy UI ---
    def _init_policy_vars(self):
        data = self.settings.get('regression_policy', {}) if hasattr(self, 'settings') else {}
        self.policy_enabled = tk.BooleanVar(value=data.get('enabled', True))
        self.policy_alert_drop = tk.DoubleVar(value=data.get('alert_drop_percent', 5.0))
        self.policy_strict_block = tk.BooleanVar(value=data.get('strict_block', False))
        self.policy_auto_rollback = tk.BooleanVar(value=data.get('auto_rollback', False))

    def create_policy_settings(self, parent):
        parent.columnconfigure(0, weight=1)
        container = ttk.Frame(parent, style='Category.TFrame')
        container.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        if not hasattr(self, 'policy_enabled'):
            self._init_policy_vars()

        ttk.Label(container, text="Evaluation & Regression Policy", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        ttk.Checkbutton(container, text="Enable Regression Policy", variable=self.policy_enabled, style='Category.TCheckbutton').grid(row=1, column=0, sticky=tk.W, pady=5)

        row_frame = ttk.Frame(container)
        row_frame.grid(row=2, column=0, sticky=tk.W)
        ttk.Label(row_frame, text="Alert if drop > %:", style='Config.TLabel').pack(side=tk.LEFT, padx=(0, 8))
        ttk.Spinbox(row_frame, from_=0.0, to=100.0, increment=0.5, textvariable=self.policy_alert_drop, width=8).pack(side=tk.LEFT)

        ttk.Checkbutton(container, text="Strict Mode: Flag training if regressions detected", variable=self.policy_strict_block, style='Category.TCheckbutton').grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Checkbutton(container, text="Auto-Rollback (not implemented)", variable=self.policy_auto_rollback, style='Category.TCheckbutton').grid(row=4, column=0, sticky=tk.W, pady=5)
        ttk.Button(container, text="💾 Save Policy", command=self.save_settings_to_file, style='Action.TButton').grid(row=5, column=0, sticky=tk.W, pady=(10,0))

    def start_log_polling(self):
        """Starts the periodic polling of the log file."""
        if self.log_poll_job:
            self.parent.after_cancel(self.log_poll_job)
        self.poll_log_file()

    def stop_log_polling(self):
        """Stops the periodic polling of the log file."""
        if self.log_poll_job:
            self.parent.after_cancel(self.log_poll_job)
            self.log_poll_job = None

    def poll_log_file(self):
        """Checks the current log file for new content and updates the display. Only polls if viewing the live log."""
        # Only poll if the currently viewed log is the live log
        if self.current_log_file != logger_util.get_log_file_path():
            self.log_poll_job = self.parent.after(2000, self.poll_log_file) # Keep scheduling to re-check if it becomes live
            return

        log_dir = DATA_DIR / "DeBug"
        list_of_files = glob.glob(str(log_dir / 'debug_log_*.txt'))
        if not list_of_files:
            self.debug_output.config(state=tk.NORMAL)
            self.debug_output.delete(1.0, tk.END)
            self.debug_output.insert(tk.END, "No log files found in DeBug directory.")
            self.debug_output.config(state=tk.DISABLED)
            self.log_poll_job = self.parent.after(2000, self.poll_log_file) # Keep polling
            return

        # Ensure we are always polling the actual latest file if 'Live Log' is selected
        actual_latest_file = max(list_of_files, key=os.path.getctime)
        if self.current_log_file != actual_latest_file:
            # This should ideally not happen if on_log_file_selected correctly sets current_log_file to the live one
            # But as a safeguard, if the live log file changes (e.g., app restart), update.
            self.current_log_file = actual_latest_file
            self.last_read_position = 0
            self.log_file_var.set("Live Log") # Ensure combobox shows Live Log
            self.debug_output.config(state=tk.NORMAL)
            self.debug_output.delete(1.0, tk.END)
            self.debug_output.insert(tk.END, f"--- Switched to live log: {os.path.basename(actual_latest_file)} ---\n\n")
            self.debug_output.config(state=tk.DISABLED)

        try:
            with open(self.current_log_file, 'r') as f:
                f.seek(self.last_read_position)
                new_content = f.read()
                if new_content:
                    # Use enhanced viewer for color coding if available
                    if hasattr(self, 'enhanced_viewer') and ENHANCED_DEBUG_AVAILABLE:
                        for line in new_content.split('\n'):
                            if line.strip():
                                self.enhanced_viewer.insert_line(line.rstrip(), auto_highlight=True)
                    else:
                        # Fallback to original
                        self.debug_output.config(state=tk.NORMAL)
                        self.debug_output.insert(tk.END, new_content)
                        self.debug_output.see(tk.END)
                        self.debug_output.config(state=tk.DISABLED)
                self.last_read_position = f.tell()

        except Exception as e:
            self.debug_output.config(state=tk.NORMAL)
            self.debug_output.insert(tk.END, f"\n--- ERROR POLLING LOG: {e} ---\n")
            self.debug_output.config(state=tk.DISABLED)
        
        self.log_poll_job = self.parent.after(2000, self.poll_log_file) # Poll every 2 seconds

    # --- Change watcher helpers -------------------------------------------------
    def _change_watcher_config_path(self) -> Path:
        prefs_dir = DATA_DIR / "user_prefs"
        prefs_dir.mkdir(parents=True, exist_ok=True)
        return prefs_dir / "change_watcher.json"

    def _load_change_watcher_settings(self) -> Dict[str, Any]:
        path = self._change_watcher_config_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                data.setdefault("enabled", False)
                data.setdefault("interval_seconds", 60)
                data.setdefault("ignore_patterns", [])
                data.setdefault("silent", True)
                data.setdefault("trusted_patterns", [])
                data.setdefault("changes_mode_enabled", False)
                normalized_patterns = []
                for entry in data.get("trusted_patterns", []):
                    token = str(entry).strip().lower()
                    if token and not token.endswith('/'):
                        token = f"{token}/"
                    if token and token not in normalized_patterns:
                        normalized_patterns.append(token)
                if not normalized_patterns:
                    normalized_patterns = list(DEFAULT_TRUSTED_PATTERNS)
                data["trusted_patterns"] = normalized_patterns
                return data
            except Exception:
                pass
        return {
            "enabled": False,
            "interval_seconds": 60,
            "ignore_patterns": [],
            "silent": True,
            "trusted_patterns": list(DEFAULT_TRUSTED_PATTERNS),
            "changes_mode_enabled": False,
        }

    def _save_change_watcher_settings(self) -> None:
        try:
            path = self._change_watcher_config_path()
            path.write_text(json.dumps(self.change_watcher_settings, indent=2), encoding='utf-8')
        except Exception as exc:
            log_message(f"SETTINGS: Failed to save change watcher settings: {exc}")

    def _apply_change_watcher_from_ui(self, initial: bool = False) -> None:
        if not hasattr(self, 'change_watcher_enabled_var'):
            return
        self.change_watcher_settings.update({
            "enabled": bool(self.change_watcher_enabled_var.get()),
            "interval_seconds": max(10, int(self.change_watcher_interval_var.get() or 60)),
            "ignore_patterns": [p.strip() for p in self.change_watcher_ignore_var.get().split(',') if p.strip()],
            "silent": bool(self.change_watcher_silent_var.get()),
            "trusted_patterns": self.change_watcher_settings.get("trusted_patterns", []),
        })
        self._save_change_watcher_settings()

        if not WATCHER_AVAILABLE:
            if hasattr(self, 'change_watcher_status_var'):
                self.change_watcher_status_var.set('Watcher unavailable')
            return

        configure_watcher(
            root_path=DATA_DIR.parent,
            history_dir=None,
            interval_seconds=self.change_watcher_settings['interval_seconds'],
            ignore_patterns=self.change_watcher_settings['ignore_patterns'],
            silent=self.change_watcher_settings['silent'],
            trusted_patterns=self.change_watcher_settings.get('trusted_patterns'),
        )
        watcher_set_trusted_patterns(self.change_watcher_settings.get('trusted_patterns') or [])

        prev_active = bool(getattr(self, '_change_watcher_active', False))
        if self.change_watcher_settings['enabled']:
            start_watcher()
            self._change_watcher_active = True
            # Only create a baseline when the user toggles this on interactively
            if not initial and not prev_active:
                try:
                    from code_change_watcher import duplicate_version as _dup
                    stats = _dup()
                    msg = f"Baselined {stats.get('files',0)} files"
                    log_message(f"[DEBUG_VIEW] {msg}")
                    try:
                        messagebox.showinfo('Change Watcher', f'{msg}.')
                    except Exception:
                        pass
                except Exception as exc:
                    log_message(f"SETTINGS: Duplicate Version during enable failed: {exc}")
            # Trigger an immediate scan so the Changes panel populates
            watcher_scan_now()
            status = 'Watcher running'
        else:
            stop_watcher()
            self._change_watcher_active = False
            status = 'Watcher disabled'

        self._sync_gatekeeper_state()

        info = get_last_scan_info() if WATCHER_AVAILABLE else None
        if info:
            status += f" • Last scan {info.get('datetime','')}"
        if hasattr(self, 'change_watcher_status_var'):
            self.change_watcher_status_var.set(status)

    def _change_watcher_interval_changed(self) -> None:
        self._apply_change_watcher_from_ui()

    def _change_watcher_scan_now(self) -> None:
        if not WATCHER_AVAILABLE:
            return
        if not self.change_watcher_settings.get('enabled'):
            messagebox.showinfo('Change Watcher', 'Enable the watcher before scanning.')
            return
        watcher_scan_now()
        self.change_watcher_status_var.set('Scan requested…')

    def _change_watcher_rebuild_baseline(self) -> None:
        if not WATCHER_AVAILABLE:
            return
        watcher_rebuild_baseline()
        self.change_watcher_status_var.set('Baseline rebuilt')

    def _on_changes_mode_toggled(self) -> None:
        enabled = bool(self.changes_mode_enabled_var.get())
        self.change_watcher_settings['changes_mode_enabled'] = enabled
        self._save_change_watcher_settings()
        self._update_changes_mode_indicator(enabled)
        self._sync_gatekeeper_state()
        # Kick an immediate scan so the conformer can appear if changes exist
        try:
            if WATCHER_AVAILABLE and bool(self.change_watcher_settings.get('enabled')) and enabled:
                watcher_scan_now()
        except Exception:
            pass
            try:
                if enabled:
                    ui_showinfo('Changes Mode', 'Changes Mode enabled. Future file edits will show a confirmation dialog with diffs.')
                else:
                    ui_showinfo('Changes Mode', 'Changes Mode disabled. File edits will be recorded without confirmation.')
            except Exception:
                pass

    def _update_changes_mode_indicator(self, enabled: Optional[bool] = None) -> None:
        if enabled is None:
            enabled = bool(self.change_watcher_settings.get('changes_mode_enabled'))
        label = 'Changes Allowed: Confirm' if enabled else 'Changes Allowed: Allowed'
        if hasattr(self, 'changes_mode_status_var'):
            self.changes_mode_status_var.set(label)

    def _sync_gatekeeper_state(self) -> None:
        if not WATCHER_AVAILABLE:
            return
        enabled = bool(self.change_watcher_settings.get('changes_mode_enabled'))
        try:
            set_gatekeeper_enabled(enabled)
            set_gate_callback(self._gatekeeper_callback if enabled else None)
        except Exception as exc:
            log_message(f"SETTINGS: Failed to sync changes mode: {exc}")

    def _on_duplicate_version(self) -> None:
        if not WATCHER_AVAILABLE:
            messagebox.showinfo('Duplicate Version', 'Change watcher service is not available.')
            return
        proceed = messagebox.askyesno(
            'Duplicate Version',
            'Create backups for all tracked files now?\n\nThis may take a moment for large projects.'
        )
        if not proceed:
            return

        btn = getattr(self, 'duplicate_version_button', None)
        if btn:
            btn.state(['disabled'])

        progress_win = tk.Toplevel(self.root)
        progress_win.title('Duplicating Version')
        progress_win.transient(self.root)
        progress_win.grab_set()
        ttk.Label(progress_win, text='Creating backups...', style='Config.TLabel').pack(padx=12, pady=(12, 6))
        status_var = tk.StringVar(value='Preparing...')
        ttk.Label(progress_win, textvariable=status_var).pack(padx=12, pady=(0, 6))
        progress_bar = ttk.Progressbar(progress_win, mode='indeterminate', length=240)
        progress_bar.pack(padx=12, pady=(0, 12))
        progress_bar.start(10)

        progress_state = {'started': False}

        def progress_callback(done: int, total: int) -> None:
            def _update():
                if not progress_state['started']:
                    progress_state['started'] = True
                    progress_bar.stop()
                    progress_bar.configure(mode='determinate', maximum=max(total, 1))
                progress_bar['value'] = done
                status_var.set(f'Duplicated {done} of {total} files...')
            try:
                self.root.after(0, _update)
            except Exception:
                pass

        def worker():
            try:
                stats = watcher_duplicate_version(progress_callback)
                message = f"Backups created for {stats.get('files', 0)} files."
                self.root.after(0, lambda: self._finish_duplicate_version(progress_win, btn, message))
            except Exception as exc:
                log_message(f"SETTINGS: Duplicate version failed: {exc}")
                self.root.after(0, lambda: self._finish_duplicate_version(progress_win, btn, f"Failed: {exc}"))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_duplicate_version(self, window: tk.Toplevel, button: Optional[ttk.Widget], message: str) -> None:
        try:
            if window.winfo_exists():
                window.grab_release()
                window.destroy()
        except Exception:
            pass
        if button:
            try:
                button.state(['!disabled'])
            except Exception:
                pass
        messagebox.showinfo('Duplicate Version', message)

    def _gatekeeper_callback(self, change_payload: Dict[str, Any]) -> bool:
        """Bridge watcher callbacks onto the Tk thread for user confirmation."""
        decision_event = threading.Event()
        result = {"decision": False}

        def _prompt():
            try:
                result['decision'] = self._prompt_change_conformer(change_payload)
            except Exception as exc:
                log_message(f"SETTINGS: Conformer prompt failed: {exc}")
                result['decision'] = False
            finally:
                decision_event.set()

        try:
            self.root.after(0, _prompt)
        except Exception:
            # If we cannot schedule onto Tk, deny by default.
            return False

        decision_event.wait()
        return bool(result['decision'])

    def _prompt_change_conformer(self, change_payload: Dict[str, Any]) -> bool:
        """Show a simple conformer dialog for pending changes."""
        file_path = change_payload.get('absolute_path') or change_payload.get('file_path', 'unknown')
        change_type = change_payload.get('change_type', 'MODIFICATION')
        diff_snippet = change_payload.get('diff_snippet') or ''
        backup_path = change_payload.get('backup_path')
        # Build a unified diff from backup/current if available
        computed_diff = ''
        try:
            if backup_path and Path(backup_path).exists() and file_path:
                old_text = Path(backup_path).read_text(encoding='utf-8', errors='ignore')
                try:
                    cur_path = Path(file_path)
                    if not cur_path.exists():
                        # absolute fallback
                        cur_path = Path(DATA_DIR.parent) / Path(change_payload.get('file_path',''))
                    new_text = cur_path.read_text(encoding='utf-8', errors='ignore')
                except Exception:
                    new_text = ''
                import difflib
                lines = difflib.unified_diff(
                    old_text.splitlines(), new_text.splitlines(),
                    fromfile='previous', tofile='current', lineterm=''
                )
                computed = "\n".join(lines)
                if computed:
                    computed_diff = computed
        except Exception:
            computed_diff = ''

        dialog = tk.Toplevel(self.root)
        dialog.title("Change Detected")
        dialog.configure(bg="#2b2b2b")
        dialog.geometry("620x420")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=f"Detected change: {change_type}", style='Heading.TLabel').pack(anchor=tk.W, padx=12, pady=(12, 4))
        ttk.Label(dialog, text=f"File: {file_path}", style='Config.TLabel').pack(anchor=tk.W, padx=12, pady=(0, 8))

        text_frame = ttk.Frame(dialog)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        diff_view = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, font=("Courier", 9), height=12)
        preview_text = computed_diff or diff_snippet
        diff_view.insert(tk.END, preview_text[:8000] if preview_text else "(no diff preview available)")
        diff_view.configure(state=tk.DISABLED)
        diff_view.pack(fill=tk.BOTH, expand=True)

        decision = {"value": False}

        def _accept():
            decision["value"] = True
            dialog.destroy()

        def _reject():
            decision["value"] = False
            dialog.destroy()

        def _see_diff():
            self._open_diff_preview(change_payload)

        button_row = ttk.Frame(dialog)
        button_row.pack(fill=tk.X, padx=12, pady=(0, 12))

        ttk.Button(button_row, text="See Diff", command=_see_diff).pack(side=tk.LEFT)
        ttk.Button(button_row, text="No", style='Danger.TButton', command=_reject).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(button_row, text="Yes", style='Action.TButton', command=_accept).pack(side=tk.RIGHT)

        dialog.wait_window()
        ok = bool(decision["value"])
        # If accepted, mark related bugs pending verification
        if ok:
            try:
                from bug_tracker import get_bug_tracker
                bt = get_bug_tracker()
                if bt:
                    rel = change_payload.get('file_path') or ''
                    bt.mark_related_bugs_pending(rel)
            except Exception:
                pass
        return ok

    def _open_diff_preview(self, change_payload: Dict[str, Any]) -> None:
        """Open a diff dialog showing the change details."""
        diff_snippet = change_payload.get('diff_snippet') or ''
        window = tk.Toplevel(self.root)
        window.title("Change Diff")
        window.geometry("720x500")
        window.configure(bg="#2b2b2b")

        text = scrolledtext.ScrolledText(window, wrap=tk.WORD, font=("Courier", 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert(tk.END, diff_snippet or "(no diff available)")
        text.configure(state=tk.DISABLED)

    # --- Bug panel settings -------------------------------------------------
    def _bug_panel_settings_path(self) -> Path:
        prefs_dir = DATA_DIR / "user_prefs"
        prefs_dir.mkdir(parents=True, exist_ok=True)
        return prefs_dir / "bug_panel_settings.json"

    def _load_bug_panel_settings(self) -> Dict[str, Any]:
        path = self._bug_panel_settings_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                self.change_watcher_settings['bug_session_only'] = bool(data.get('session_only', True))
                return data
            except Exception:
                pass
        return {
            "auto_refresh": True,
            "interval_seconds": 5,
            "session_only": True,
        }

    def _save_bug_panel_settings(self, data: Dict[str, Any]) -> None:
        try:
            path = self._bug_panel_settings_path()
            path.write_text(json.dumps(data, indent=2), encoding='utf-8')
            self.change_watcher_settings['bug_session_only'] = bool(data.get('session_only', True))
        except Exception as exc:
            log_message(f"SETTINGS: Failed to persist bug panel settings: {exc}")

    def create_blueprints_tab(self, parent):
        """Create System Blueprints documentation tab"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # Scrollable frame
        canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        content_frame = ttk.Frame(canvas)

        content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        # Header + Blueprint selector toolbar
        header_section = ttk.Frame(content_frame)
        header_section.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(
            header_section,
            text="🗺️ OpenCode Trainer System Architecture",
            font=("Arial", 14, "bold"),
            foreground='#4db8ff'
        ).grid(row=0, column=0, columnspan=4, sticky=tk.W)
        ttk.Label(
            header_section,
            text="Complete End-to-End Integrated Training Pipeline",
            font=("Arial", 10),
            foreground='#888888'
        ).grid(row=1, column=0, columnspan=4, sticky=tk.W, pady=(0,4))

        # Live debug blueprint (auto-updating JSON) ------------------------
        live_section = ttk.LabelFrame(
            content_frame,
            text="🛰️ Live Debug System Blueprint",
            style='TLabelframe'
        )
        live_section.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 12))
        live_section.columnconfigure(0, weight=1)
        live_section.rowconfigure(1, weight=1)

        live_header = ttk.Frame(live_section)
        live_header.grid(row=0, column=0, sticky=tk.EW, padx=8, pady=(6, 4))
        live_header.columnconfigure(1, weight=1)
        self._bp_live_last_updated_var = tk.StringVar(value="Last updated: --")
        ttk.Label(
            live_header,
            textvariable=self._bp_live_last_updated_var,
            font=("Arial", 10, "bold")
        ).grid(row=0, column=0, sticky=tk.W)
        self._bp_live_path_var = tk.StringVar(
            value="Source: Data/blueprints/debug_system_blueprint.json"
        )
        ttk.Label(
            live_header,
            textvariable=self._bp_live_path_var,
            font=("Arial", 9),
            foreground="#888888"
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(2, 0))
        self._bp_live_status_summary_var = tk.StringVar(value="Status counts not available.")
        ttk.Label(
            live_header,
            textvariable=self._bp_live_status_summary_var,
            font=("Arial", 9),
            foreground="#cccccc",
            wraplength=520,
            justify=tk.LEFT
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(4, 0))
        # Manual refresh button
        refresh_btn = ttk.Button(
            live_header,
            text="Refresh Now",
            style='Select.TButton'
        )
        refresh_btn.grid(row=0, column=2, rowspan=2, sticky=tk.E, padx=(12, 0))

        # Split area for active bugs and path index
        live_split = ttk.Frame(live_section)
        live_split.grid(row=1, column=0, sticky=tk.NSEW, padx=8, pady=(0, 6))
        live_split.columnconfigure(0, weight=1)
        live_split.columnconfigure(1, weight=1)
        live_split.rowconfigure(0, weight=1)

        # Active bugs tree -------------------------------------------------
        active_frame = ttk.LabelFrame(live_split, text="Active Bugs", style='TLabelframe')
        active_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 6))
        active_frame.columnconfigure(0, weight=1)
        active_frame.rowconfigure(0, weight=1)
        active_columns = ("bug", "status", "error", "file", "line", "last_seen")
        self._bp_active_tree = ttk.Treeview(
            active_frame,
            columns=active_columns,
            show="headings",
            height=8
        )
        self._bp_active_tree.heading("bug", text="Bug ID")
        self._bp_active_tree.heading("status", text="Status")
        self._bp_active_tree.heading("error", text="Error")
        self._bp_active_tree.heading("file", text="File")
        self._bp_active_tree.heading("line", text="Line")
        self._bp_active_tree.heading("last_seen", text="Last Seen")
        self._bp_active_tree.column("bug", width=150, anchor=tk.W)
        self._bp_active_tree.column("status", width=90, anchor=tk.W)
        self._bp_active_tree.column("error", width=120, anchor=tk.W)
        self._bp_active_tree.column("file", width=160, anchor=tk.W)
        self._bp_active_tree.column("line", width=60, anchor=tk.CENTER)
        self._bp_active_tree.column("last_seen", width=150, anchor=tk.W)
        active_scroll = ttk.Scrollbar(active_frame, orient=tk.VERTICAL, command=self._bp_active_tree.yview)
        self._bp_active_tree.configure(yscrollcommand=active_scroll.set)
        self._bp_active_tree.grid(row=0, column=0, sticky=tk.NSEW)
        active_scroll.grid(row=0, column=1, sticky=tk.NS)

        # Path index tree --------------------------------------------------
        path_frame = ttk.LabelFrame(live_split, text="Path Index", style='TLabelframe')
        path_frame.grid(row=0, column=1, sticky=tk.NSEW)
        path_frame.columnconfigure(0, weight=1)
        path_frame.rowconfigure(0, weight=1)
        path_columns = ("details",)
        self._bp_path_tree = ttk.Treeview(
            path_frame,
            columns=path_columns,
            show="tree headings",
            height=8
        )
        self._bp_path_tree.heading("#0", text="Path")
        self._bp_path_tree.heading("details", text="Details")
        self._bp_path_tree.column("#0", width=220, anchor=tk.W)
        self._bp_path_tree.column("details", width=260, anchor=tk.W)
        path_scroll = ttk.Scrollbar(path_frame, orient=tk.VERTICAL, command=self._bp_path_tree.yview)
        self._bp_path_tree.configure(yscrollcommand=path_scroll.set)
        self._bp_path_tree.grid(row=0, column=0, sticky=tk.NSEW)
        path_scroll.grid(row=0, column=1, sticky=tk.NS)

        # Metadata rows ----------------------------------------------------
        meta_frame = ttk.Frame(live_section)
        meta_frame.grid(row=2, column=0, sticky=tk.EW, padx=8, pady=(0, 6))
        meta_frame.columnconfigure(1, weight=1)
        self._bp_live_latest_fix_var = tk.StringVar(value="Latest fix: --")
        self._bp_live_latest_backup_var = tk.StringVar(value="Latest backup: --")
        ttk.Label(
            meta_frame,
            textvariable=self._bp_live_latest_fix_var,
            font=("Arial", 9),
            foreground="#cccccc"
        ).grid(row=0, column=0, sticky=tk.W, pady=(2, 0))
        ttk.Label(
            meta_frame,
            textvariable=self._bp_live_latest_backup_var,
            font=("Arial", 9),
            foreground="#cccccc"
        ).grid(row=1, column=0, sticky=tk.W, pady=(2, 0))

        notes_frame = ttk.LabelFrame(live_section, text="System Notes", style='TLabelframe')
        notes_frame.grid(row=3, column=0, sticky=tk.EW, padx=8, pady=(0, 8))
        self._bp_live_notes_var = tk.StringVar(value="No notes available.")
        ttk.Label(
            notes_frame,
            textvariable=self._bp_live_notes_var,
            font=("Arial", 9),
            foreground="#a0a0a0",
            justify=tk.LEFT,
            wraplength=760
        ).pack(fill=tk.X, expand=True, padx=8, pady=6)

        # Live blueprint helpers ------------------------------------------
        blueprint_json_path = Path('Data/blueprints/debug_system_blueprint.json')
        self._blueprint_json_path = blueprint_json_path
        self._blueprint_last_mtime: Optional[float] = None
        self._blueprint_poll_job: Optional[str] = None

        from datetime import datetime

        def _format_timestamp(raw: Optional[str]) -> str:
            if not raw:
                return "--"
            try:
                return datetime.fromisoformat(str(raw)).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                return str(raw)

        def _load_live_blueprint() -> Optional[Dict[str, Any]]:
            if not blueprint_json_path.exists():
                return None
            try:
                return json.loads(blueprint_json_path.read_text(encoding='utf-8'))
            except Exception as exc:
                log_message(f"SETTINGS: Failed to load blueprint JSON: {exc}")
                return None

        def _render_live_blueprint(payload: Optional[Dict[str, Any]]) -> None:
            if not payload:
                self._bp_live_last_updated_var.set("Last updated: --")
                self._bp_live_status_summary_var.set("Blueprint data unavailable.")
                self._bp_live_latest_fix_var.set("Latest fix: --")
                self._bp_live_latest_backup_var.set("Latest backup: --")
                self._bp_live_notes_var.set("System notes unavailable.")
                for tree in (self._bp_active_tree, self._bp_path_tree):
                    for item in tree.get_children():
                        tree.delete(item)
                return

            generated = payload.get("generated_at")
            self._bp_live_last_updated_var.set(f"Last updated: {_format_timestamp(generated)}")
            status_counts = payload.get("status_counts") or {}
            if status_counts:
                formatted = " | ".join(
                    f"{key.replace('_', ' ').title()}: {value}"
                    for key, value in sorted(status_counts.items())
                )
            else:
                formatted = "No status counts recorded."
            self._bp_live_status_summary_var.set(formatted)

            # Active bugs
            for item in self._bp_active_tree.get_children():
                self._bp_active_tree.delete(item)
            for bug in payload.get("active_bugs", []):
                file_path = bug.get("file_path") or ""
                file_name = Path(file_path).name if file_path else "(unknown)"
                self._bp_active_tree.insert(
                    "",
                    tk.END,
                    values=(
                        bug.get("bug_id"),
                        bug.get("status"),
                        bug.get("error_type"),
                        file_name,
                        bug.get("line_number") or "",
                        _format_timestamp(bug.get("last_seen"))
                    )
                )

            # Path index tree
            for item in self._bp_path_tree.get_children():
                self._bp_path_tree.delete(item)
            for file_path, meta in sorted((payload.get("path_index") or {}).items()):
                base = Path(file_path).name or file_path
                parent = self._bp_path_tree.insert("", tk.END, text=base, values=(file_path,))
                for bug in meta.get("bugs", []):
                    detail = (
                        f"{bug.get('status', 'unknown').title()} • "
                        f"Line {bug.get('line_number') or '?'} • "
                        f"{bug.get('error_type') or ''}"
                    ).strip()
                    self._bp_path_tree.insert(
                        parent,
                        tk.END,
                        text=bug.get("bug_id"),
                        values=(detail,)
                    )

            latest_fix = payload.get("latest_fix")
            if latest_fix:
                self._bp_live_latest_fix_var.set(
                    f"Latest fix: {_format_timestamp(latest_fix.get('timestamp'))} • "
                    f"{latest_fix.get('bug_id')} • {latest_fix.get('action_id') or 'action'}"
                )
            else:
                self._bp_live_latest_fix_var.set("Latest fix: --")

            latest_backup = payload.get("latest_backup")
            if latest_backup:
                self._bp_live_latest_backup_var.set(
                    f"Latest backup: {_format_timestamp(latest_backup.get('timestamp'))} • "
                    f"{latest_backup.get('bug_id')} • {latest_backup.get('action_id') or 'backup'}"
                )
            else:
                self._bp_live_latest_backup_var.set("Latest backup: --")

            notes = payload.get("system_notes") or []
            if notes:
                self._bp_live_notes_var.set("\n".join(f"• {note}" for note in notes))
            else:
                self._bp_live_notes_var.set("No system notes recorded.")

        def _refresh_live_blueprint(force: bool = False) -> None:
            try:
                mtime = blueprint_json_path.stat().st_mtime
            except FileNotFoundError:
                mtime = None
            if not force and mtime is not None and self._blueprint_last_mtime is not None:
                if mtime <= self._blueprint_last_mtime:
                    return
            payload = _load_live_blueprint()
            if mtime is not None:
                self._blueprint_last_mtime = mtime
            _render_live_blueprint(payload)

        def _schedule_blueprint_poll() -> None:
            if self._blueprint_poll_job:
                try:
                    self.root.after_cancel(self._blueprint_poll_job)
                except Exception:
                    pass
            def _poll():
                _refresh_live_blueprint()
                self._blueprint_poll_job = self.root.after(5000, _poll)
            self._blueprint_poll_job = self.root.after(5000, _poll)

        def _manual_refresh():
            _refresh_live_blueprint(force=True)

        refresh_btn.configure(command=_manual_refresh)
        self._refresh_live_blueprint_view = _manual_refresh

        def _cancel_blueprint_poll(_event=None):
            if self._blueprint_poll_job:
                try:
                    self.root.after_cancel(self._blueprint_poll_job)
                except Exception:
                    pass
                self._blueprint_poll_job = None

        try:
            self.root.bind("<Destroy>", _cancel_blueprint_poll, add="+")
        except Exception:
            pass

        _refresh_live_blueprint(force=True)
        _schedule_blueprint_poll()

        # Blueprint selector row
        header_section.columnconfigure(1, weight=1)
        ttk.Label(header_section, text='Blueprint:', style='CategoryPanel.TLabel').grid(row=2, column=0, sticky=tk.W, padx=(0,6))
        self.bp_select_var = tk.StringVar()
        self.bp_selector = ttk.Combobox(header_section, textvariable=self.bp_select_var, state='readonly')
        self.bp_selector.grid(row=2, column=1, sticky=tk.EW)
        ttk.Button(header_section, text='Update Blueprint', style='Select.TButton', command=lambda: self._clone_increment_blueprint()).grid(row=2, column=2, padx=6)
        ttk.Button(header_section, text='Edit', style='Action.TButton', command=lambda: self._open_blueprint_editor()).grid(row=2, column=3)

        # Blueprint preview area
        preview_frame = ttk.LabelFrame(content_frame, text='📄 Blueprint Preview', style='TLabelframe')
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        self.bp_preview = scrolledtext.ScrolledText(preview_frame, wrap=tk.WORD, font=("Arial", 9), bg="#1e1e1e", fg="#dcdcdc")
        self.bp_preview.grid(row=0, column=0, sticky=tk.NSEW)

        # Helper methods for blueprints
        def _registry_path():
            return Path('extras/blueprints/blueprint_registry.txt')

        def _list_blueprints_from_fs():
            base = Path('extras/blueprints')
            files = []
            try:
                for p in sorted(base.glob('Trainer_Blue_Print_*.txt')):
                    files.append(p.name)
                snapshots_dir = base / 'version_snapshots'
                if snapshots_dir.exists():
                    for p in sorted(snapshots_dir.glob('System_Blue_Print_*.txt')):
                        files.append(f"version_snapshots/{p.name}")
            except Exception:
                pass
            return files

        def _read_registry():
            rp = _registry_path()
            if rp.exists():
                try:
                    return [ln.strip() for ln in rp.read_text(encoding='utf-8').splitlines() if ln.strip() and not ln.strip().startswith('#')]
                except Exception:
                    return []
            # bootstrap registry with FS scan
            return _list_blueprints_from_fs()

        def _write_registry(names):
            try:
                Path('extras/blueprints').mkdir(parents=True, exist_ok=True)
                text = '\n'.join(names)
                _registry_path().write_text((text + '\n') if text else '', encoding='utf-8')
            except Exception:
                pass

        def _set_preview(text):
            try:
                self.bp_preview.config(state=tk.NORMAL)
                self.bp_preview.delete('1.0', tk.END)
                self.bp_preview.insert(tk.END, text)
                self.bp_preview.config(state=tk.DISABLED)
            except Exception:
                pass

        def _load_selected_into_preview():
            sel = self.bp_select_var.get().strip()
            if not sel:
                _set_preview('')
                return
            path = Path('extras/blueprints')/sel
            try:
                txt = path.read_text()
            except Exception as e:
                txt = f"Failed to load {path}: {e}"
            _set_preview(txt)

        def _parse_version_from_name(name):
            import re
            m = re.search(r'v(\d+)\.(\d+)', name)
            if not m:
                return None
            return int(m.group(1)), int(m.group(2))

        def _bump_minor(v):
            if not v:
                return (2, 1)
            return (v[0], v[1] + 1)

        def _update_content_version(text, new_ver_tuple):
            new_ver = f"{new_ver_tuple[0]}.{new_ver_tuple[1]}"
            lines = text.splitlines()
            out = []
            from datetime import date
            today = date.today().isoformat()
            for ln in lines:
                if ln.strip().startswith('Version:'):
                    out.append(f"  Version: {new_ver}")
                elif 'Blueprint v' in ln:
                    # e.g., "OpenCode Trainer System - Blueprint v2.0"
                    import re
                    out.append(re.sub(r'Blueprint v\d+\.\d+', f'Blueprint v{new_ver}', ln))
                elif ln.strip().startswith('Date:'):
                    out.append(f"  Date: {today}")
                else:
                    out.append(ln)
            return '\n'.join(out) + ('\n' if text.endswith('\n') else '')

        def _ensure_registry_seeded():
            names = _read_registry()
            fs_names = _list_blueprints_from_fs()
            for entry in fs_names:
                if entry not in names:
                    names.append(entry)
            if not names:
                # create seed with v2.0 if missing
                seed = 'Trainer_Blue_Print_v2.0.txt'
                if (Path('extras/blueprints')/seed).exists():
                    names = [seed]
            _write_registry(names)
            return names

        vm = None
        active_version_id: Optional[str] = None
        if VERSION_MANAGER_AVAILABLE:
            try:
                vm = VersionManager()
                active_version_id = vm.registry.get('active_version')
            except Exception as exc:
                vm = None
                log_message(f"SETTINGS: Version manager access failed: {exc}")

        def _find_latest_snapshot_for_version(version_id: Optional[str], names: List[str]) -> Optional[str]:
            if not version_id:
                return None
            import re as _re
            sanitized = _re.sub(r'[^A-Za-z0-9]+', '_', version_id).strip('_') or "version"
            prefix = f"version_snapshots/System_Blue_Print_{sanitized}_"
            matches = [name for name in names if name.startswith(prefix)]
            if not matches:
                return None
            return sorted(matches)[-1]

        def _refresh_selector(select_name=None):
            names = _ensure_registry_seeded()
            self.bp_selector['values'] = names
            if select_name and select_name in names:
                self.bp_select_var.set(select_name)
            elif not self.bp_select_var.get():
                candidate = _find_latest_snapshot_for_version(active_version_id, names)
                if candidate:
                    self.bp_select_var.set(candidate)
                elif names:
                    self.bp_select_var.set(names[-1])
            _load_selected_into_preview()

        # Bind events and expose handlers on self
        self._refresh_blueprint_selector = _refresh_selector
        self._load_blueprint_into_preview = _load_selected_into_preview
        self._read_blueprint_registry = _read_registry
        self._write_blueprint_registry = _write_registry
        self._parse_bp_version = _parse_version_from_name
        self._bump_bp_minor = _bump_minor
        self._update_content_version = _update_content_version

        try:
            self.bp_selector.bind('<<ComboboxSelected>>', lambda e: _load_selected_into_preview())
        except Exception:
            pass

        # Public methods: clone/update and editor
        def _clone_increment_blueprint():
            names = _read_registry()
            sel = self.bp_select_var.get().strip() or (names[-1] if names else '')
            if not sel:
                messagebox.showinfo('Update Blueprint', 'No blueprint selected.')
                return
            src = Path('extras/blueprints')/sel
            if not src.exists():
                messagebox.showerror('Update Blueprint', f'Source file not found: {src}')
                return
            v = _parse_version_from_name(sel)
            new_v = _bump_minor(v)
            base = 'Trainer_Blue_Print'
            new_name = f"{base}_v{new_v[0]}.{new_v[1]}.txt"
            dst = Path('extras/blueprints')/new_name
            if dst.exists():
                messagebox.showerror('Update Blueprint', f'Target exists: {dst.name}')
                return
            try:
                text = src.read_text()
                updated = _update_content_version(text, new_v)
                dst.write_text(updated)
            except Exception as e:
                messagebox.showerror('Update Blueprint', f'Failed to clone: {e}')
                return
            # Update registry
            names.append(new_name)
            _write_registry(names)
            # Refresh selector and preview to new file
            _refresh_selector(select_name=new_name)
            messagebox.showinfo('Update Blueprint', f'Created {new_name}')

        def _open_blueprint_editor():
            sel = self.bp_select_var.get().strip()
            if not sel:
                messagebox.showinfo('Edit Blueprint', 'No blueprint selected.')
                return
            path = Path('extras/blueprints')/sel
            top = tk.Toplevel(self.root); top.title(f'Edit: {sel}')
            frm = ttk.Frame(top, padding=8); frm.pack(fill=tk.BOTH, expand=True)
            frm.columnconfigure(0, weight=1); frm.rowconfigure(0, weight=1)
            txt = scrolledtext.ScrolledText(frm, wrap=tk.WORD, font=("Arial", 9), bg='#1e1e1e', fg='#dcdcdc')
            txt.grid(row=0, column=0, sticky=tk.NSEW)
            btns = ttk.Frame(frm); btns.grid(row=1, column=0, sticky=tk.E)
            def _save():
                try:
                    path.write_text(txt.get('1.0', tk.END))
                    # refresh preview
                    _load_selected_into_preview()
                    messagebox.showinfo('Save', 'Blueprint saved.')
                except Exception as e:
                    messagebox.showerror('Save Failed', str(e))
            def _copy():
                try:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(txt.get('1.0', tk.END))
                    messagebox.showinfo('Copied', 'Blueprint copied to clipboard.')
                except Exception:
                    pass
            ttk.Button(btns, text='Copy to Clipboard', style='Select.TButton', command=_copy).pack(side=tk.RIGHT, padx=4)
            ttk.Button(btns, text='Save', style='Action.TButton', command=_save).pack(side=tk.RIGHT, padx=4)
            try:
                txt.insert(tk.END, path.read_text())
            except Exception as e:
                txt.insert(tk.END, f'Failed to open {path}: {e}')

        # Attach methods to instance for button callbacks
        self._clone_increment_blueprint = _clone_increment_blueprint
        self._open_blueprint_editor = _open_blueprint_editor

        # Seed registry file if missing and load selector
        try:
            Path('extras/blueprints').mkdir(parents=True, exist_ok=True)
            # Ensure registry includes v2.0 at least
            reg = _ensure_registry_seeded()
            if not reg:
                # create registry pointing to v2.0 if exists
                if (Path('extras/blueprints')/'Trainer_Blue_Print_v2.0.txt').exists():
                    _write_registry(['Trainer_Blue_Print_v2.0.txt'])
            self._refresh_blueprint_selector()
        except Exception:
            pass

        # Overview Section
        overview_section = ttk.LabelFrame(content_frame, text="📋 System Overview", style='TLabelframe')
        overview_section.pack(fill=tk.X, padx=10, pady=10)

        overview_text = """The OpenCode Trainer integrates multiple subsystems to provide a complete model lifecycle management platform:

        ✓ Model Lineage Tracking - Track model genealogy from base to fine-tuned versions
        ✓ Dual Skill Verification - Runtime usage validation vs evaluation test results
        ✓ Automated Training Data Generation - Multiple sources for training data creation
        ✓ Regression Detection - Identify skill degradation with auto-correction
        ✓ Complete Workflow Integration - Seamless flow from download to deployment"""

        overview_label = ttk.Label(
            overview_section,
            text=overview_text,
            font=("Arial", 9),
            foreground='#cccccc',
            justify=tk.LEFT,
            wraplength=700
        )
        overview_label.pack(padx=10, pady=10, anchor=tk.W)

        # Integrated Workflow Section
        workflow_section = ttk.LabelFrame(content_frame, text="🔄 Complete Integrated Workflow", style='TLabelframe')
        workflow_section.pack(fill=tk.X, padx=10, pady=10)

        workflow_text = """STEP 1: Model Download & Initial Evaluation
        • Download base model (e.g., Qwen 0.5B) to Models directory
        • Convert to GGUF format
        • Run initial evaluation tests (Models Tab → Evaluate)
        • Baseline skills recorded (claimed skills from tests)

STEP 2: Runtime Validation & Data Collection
        • Enable "Training Mode" in Custom Code Chat Interface
        • Use the model with real tasks and tool calls
        • ToolCallLogger captures every tool invocation with success/failure
        • Real-time skill scoring updated (verified skills from actual usage)
        • ChatHistoryManager saves conversations for later extraction

STEP 3: Skill Verification & Gap Analysis
        • Models Tab displays DUAL skill view:
          - Verified (Runtime): ≥80% success rate, actual usage proof
          - Claimed (Evaluation): Test results, may be false positives
          - Failed: <80% success rate, needs training
        • Identify gaps: skills with good eval but poor runtime = false positives
        • Identify needs: skills with 0% runtime usage = untrained capabilities

STEP 4: Automated Training Data Generation
        Multiple sources automatically create training data:
        • Chat History Extraction: Extract successful tool usage patterns
        • Runtime Log Conversion: Convert tool call logs to training format
        • Corrective Data Generation: Auto-generate examples for failed skills
        All outputs saved to Training_Data-Sets/ directory

STEP 5: LoRA Fine-Tuning with Lineage Tracking
        • Select generated training data in Training Tab
        • Configure LoRA parameters (r=16, alpha=32, etc.)
        • TrainingEngine automatically:
          - Fine-tunes with adapters
          - Records lineage (base model → adapter → metadata)
          - Runs post-training evaluation
          - Saves results to Models directory

STEP 6: Regression Detection & Continuous Improvement
        • EvaluationEngine compares new eval to baseline
        • Detects regressions: skills that dropped >5% accuracy
        • Auto-generates corrective training data targeting failed skills
        • Provides re-training recommendations
        • Complete cycle: evaluate → identify issues → generate fixes → retrain"""

        workflow_label = ttk.Label(
            workflow_section,
            text=workflow_text,
            font=("Courier", 8),
            foreground='#aaaaaa',
            justify=tk.LEFT,
            wraplength=700
        )
        workflow_label.pack(padx=10, pady=10, anchor=tk.W)

        # System Integration Map
        integration_section = ttk.LabelFrame(content_frame, text="🔗 System Integration Map", style='TLabelframe')
        integration_section.pack(fill=tk.X, padx=10, pady=10)

        integration_text = """┌─────────────────────────────────────────────────────────────┐
│                    DATA FLOW INTEGRATION                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ToolCallLogger ──────┬──────> RuntimeToTrainingConverter  │
│      (JSONL logs)     │              ↓                      │
│                       │     Training Data (JSONL)           │
│                       │              ↓                      │
│  ChatHistoryManager ──┤──────> TrainingEngine               │
│      (conversations)  │         (LoRA fine-tune)            │
│                       │              ↓                      │
│  EvaluationEngine ────┤──────> LineageTracker              │
│      (test reports)   │         (model genealogy)           │
│                       │              ↓                      │
│  config.py ───────────┘──────> Models Tab Display          │
│  (_get_runtime_skills)           (dual verification)       │
│                                                             │
└─────────────────────────────────────────────────────────────┘

KEY INTEGRATION POINTS:
• ToolCallLogger → RuntimeSkills: Real-time scoring in config.py
• ChatHistoryManager → Training Data: Extract successful patterns
• EvaluationEngine → Baseline Comparison: Detect regressions
• TrainingEngine → LineageTracker: Record model genealogy
• Models Tab: Merge runtime + evaluation skills for display"""

        integration_label = ttk.Label(
            integration_section,
            text=integration_text,
            font=("Courier", 8),
            foreground='#88ff88',
            justify=tk.LEFT
        )
        integration_label.pack(padx=10, pady=10, anchor=tk.W)

        # Key Components Section
        components_section = ttk.LabelFrame(content_frame, text="⚙️ Key System Components", style='TLabelframe')
        components_section.pack(fill=tk.X, padx=10, pady=10)

        components_text = """LINEAGE TRACKER (tabs/custom_code_tab/lineage_tracker.py)
• Singleton pattern for model genealogy tracking
• Records: base model, adapter path, training date, metadata
• File: Training_Data-Sets/ModelLineage/lineage.json
• Integration: Called automatically by TrainingEngine after training

TOOL CALL LOGGER (tabs/custom_code_tab/tool_call_logger.py)
• JSONL-based persistent logging of all tool calls
• Tracks: tool name, arguments, result, success/failure, timestamp
• Enhanced validation: Multi-level success detection
• File: Training_Data-Sets/ToolCallLogs/{model_name}_calls.jsonl
• Integration: Chat interface logs every tool execution

RUNTIME TO TRAINING CONVERTER (tabs/custom_code_tab/runtime_to_training.py)
• Converts tool call logs to OpenAI training format
• Generates corrective training data from failures
• Creates proper message sequences: user → assistant → tool → assistant
• Output: Training_Data-Sets/Training/{model}_runtime_{timestamp}.jsonl

CHAT HISTORY MANAGER (tabs/custom_code_tab/chat_history_manager.py)
• Persistent conversation storage with training extraction
• Filters by tool usage count and success rate
• Extracts complete tool usage patterns
• File: Training_Data-Sets/ChatHistories/{session_id}.json

EVALUATION ENGINE (Data/evaluation_engine.py)
• Test suite execution with regression detection
• Compares current results to baseline (first eval)
• Auto-triggers corrective training on regression
• Reports: Training_Data-Sets/Evaluations/{model}_eval_report.json

TRAINING ENGINE (Data/training_engine.py)
• LoRA fine-tuning with Unsloth
• Automatic post-training evaluation
• Lineage recording after every training run
• Output: Models/{model_name}/ (adapter + merged model)

MODELS TAB (tabs/models_tab/models_tab.py)
• Dual skill verification display:
  - Verified Runtime: Green, ≥80% success
  - Unverified Eval: Yellow, low/no runtime usage
  - Failed Runtime: Red, <80% success
• Merges _get_runtime_skills() + get_model_skills()
• Shows skill source: (Runtime/Eval/Both)"""

        components_label = ttk.Label(
            components_section,
            text=components_text,
            font=("Courier", 8),
            foreground='#ffaa88',
            justify=tk.LEFT
        )
        components_label.pack(padx=10, pady=10, anchor=tk.W)

        # Data Flow Section
        dataflow_section = ttk.LabelFrame(content_frame, text="📊 Data Persistence & Storage", style='TLabelframe')
        dataflow_section.pack(fill=tk.X, padx=10, pady=10)

        dataflow_text = """Training_Data-Sets/
├── ChatHistories/           # Saved conversations
│   ├── {session_id}.json
│   └── chat_index.json
├── ToolCallLogs/            # Runtime tool execution logs
│   └── {model_name}_calls.jsonl
├── ModelLineage/            # Model genealogy tracking
│   └── lineage.json
├── Evaluations/             # Test results and baselines
│   └── {model_name}_eval_report.json
└── Training/                # Generated training data
    ├── {model}_runtime_{timestamp}.jsonl
    ├── {model}_corrective_{timestamp}.jsonl
    └── chat_extracted_{model}_{timestamp}.jsonl

Models/
└── {model_name}/
    ├── adapter_model.safetensors  # LoRA adapter weights
    ├── adapter_config.json
    └── model_merged.gguf          # Final merged GGUF

JSONL Format (training data):
{"messages": [
  {"role": "system", "content": "..."},
  {"role": "user", "content": "..."},
  {"role": "assistant", "content": "...", "tool_calls": [...]},
  {"role": "tool", "content": "...", "tool_call_id": "..."},
  {"role": "assistant", "content": "..."}
]}"""

        dataflow_label = ttk.Label(
            dataflow_section,
            text=dataflow_text,
            font=("Courier", 8),
            foreground='#ffdd88',
            justify=tk.LEFT
        )
        dataflow_label.pack(padx=10, pady=10, anchor=tk.W)

        # Development Blueprint v2 Section (Internal)
        dev_section = ttk.LabelFrame(content_frame, text="🧭 Development Blueprint (v2)", style='TLabelframe')
        dev_section.pack(fill=tk.X, padx=10, pady=10)

        dev_text = """SCOPE & STATUS (Internal Artifact)

COMPLETED IN V2
• Temperature Controls: Legacy header controls removed; Manual/Auto persisted; bottom indicator authoritative and accurate; metadata includes temp_mode; Quick View shows Temp Mode.
• Conversations QoL: Rename Chat (Chat + Projects); Projects bottom indicators de-duplicated.
• ToDo v2: Categories (Tasks, Bugs, Work-Orders, Notes, Completed); priority (High/Medium/Low) with colors; creation flow (Category→Priority→Title→Details); inline edit; Mark Complete → green Completed.

IN FLIGHT
• Agents Panel: Receive selections from Collections; display, select, and persist agent sets.
• Orchestrator Wiring: Agent types bound to type-variant training pipeline; expose tool chain controls; log telemetry.
• Dataset Auto-Generation: Profiles per type variant; synthetic generation with provenance; versioned storage.
• Evaluation Suites: Registry, schema-aware checks, multi-metric scoring; trend and baseline compare.
• End-to-End Pipeline: Agents → Profiles → Training → Eval → Compare; resumable runs and artifact indexing.

REMOVED (REDUNDANT)
• Legacy temperature header label/slider/icon (functional duplicate of Quick Actions popup + indicator).

NOTES
• UI state keys: extend the indicator state-key pattern used for temperature to other indicators to avoid duplication across tabs.
• Docs: See extras/blueprints/Trainer_Blue_Print_v2.0.txt for full external blueprint; this section reflects the GUI-internal dev plan.
"""

        dev_label = ttk.Label(
            dev_section,
            text=dev_text,
            font=("Arial", 9),
            foreground='#b8e2ff',
            justify=tk.LEFT,
            wraplength=700
        )
        dev_label.pack(padx=10, pady=10, anchor=tk.W)

    def create_help_tab(self, parent):
        """Create Help & Guide tab"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # Scrollable frame
        canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        content_frame = ttk.Frame(canvas)

        content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        # Header
        header_section = ttk.Frame(content_frame)
        header_section.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(
            header_section,
            text="📖 OpenCode Trainer User Guide",
            font=("Arial", 14, "bold"),
            foreground='#4db8ff'
        ).pack(anchor=tk.W)
        ttk.Label(
            header_section,
            text="Complete guide to using the integrated training pipeline",
            font=("Arial", 10),
            foreground='#888888'
        ).pack(anchor=tk.W)

        # Quick Start Section
        quickstart_section = ttk.LabelFrame(content_frame, text="🚀 Quick Start Guide", style='TLabelframe')
        quickstart_section.pack(fill=tk.X, padx=10, pady=10)

        quickstart_text = """1. DOWNLOAD A MODEL
   • Go to Models Tab
   • Click "Download Model from Hugging Face"
   • Enter model ID (e.g., "Qwen/Qwen2.5-0.5B")
   • Wait for download and GGUF conversion

2. EVALUATE BASELINE SKILLS
   • Select your model in Models Tab
   • Click "Evaluate Model"
   • Review baseline skills in Skills section

3. COLLECT RUNTIME DATA
   • Go to Custom Code Tab → Chat Interface
   • Enable "Training Mode" checkbox
   • Use the model for real tasks with tool calls
   • System automatically logs all tool usage

4. VERIFY REAL SKILLS
   • Return to Models Tab
   • Review Skills display showing:
     - Verified Runtime (green): Actually works
     - Claimed Eval (yellow): Test says it works
     - Failed (red): Doesn't work in practice

5. GENERATE TRAINING DATA
   • In Custom Code Chat Interface:
     - Click "Export Runtime to Training" for tool logs
     - Click "Extract Chat Training Data" for conversations
   • Or use Evaluation Tab for corrective data generation

6. FINE-TUNE THE MODEL
   • Go to Training Tab
   • Select generated training data file
   • Configure LoRA settings (defaults work well)
   • Click "Start Training"
   • System auto-evaluates and records lineage

7. VERIFY IMPROVEMENTS
   • Check Models Tab Skills display
   • Runtime scores should improve
   • Re-train with corrective data if regressions detected"""

        quickstart_label = ttk.Label(
            quickstart_section,
            text=quickstart_text,
            font=("Courier", 8),
            foreground='#cccccc',
            justify=tk.LEFT
        )
        quickstart_label.pack(padx=10, pady=10, anchor=tk.W)

        # Training Mode Section
        training_mode_section = ttk.LabelFrame(content_frame, text="🎯 Using Training Mode", style='TLabelframe')
        training_mode_section.pack(fill=tk.X, padx=10, pady=10)

        training_mode_text = """WHAT IS TRAINING MODE?
Training Mode enables real-time data collection during chat interactions.
When enabled, the system logs every tool call with detailed success metrics.

HOW TO ENABLE:
1. Go to Custom Code Tab → Chat Interface sub-tab
2. Check the "Training Mode" checkbox at the top
3. Green indicator shows mode is active

WHAT GETS COLLECTED:
✓ Every tool call (name, arguments, result)
✓ Success/failure status with enhanced validation
✓ User message context for each tool call
✓ Complete conversation history
✓ Timestamp and execution metadata

WHERE DATA IS SAVED:
• Tool Call Logs: Training_Data-Sets/ToolCallLogs/{model}_calls.jsonl
• Chat History: Training_Data-Sets/ChatHistories/{session_id}.json

BEST PRACTICES:
• Enable for new/unverified models to collect baseline data
• Disable for production use after sufficient data collected
• Use diverse tasks to cover multiple tool types
• Review Models Tab regularly to check skill improvement

AUTO‑TRAINING (Hands‑Free, Custom Code → Training → Models):
• Quick Actions (⚙️) → 🏋️ Training Mode ON (button turns green)
• Failures/refusals generate strict JSONL automatically (Tools/auto_runtime_*.jsonl)
• Training tab auto‑selects dataset and saves profile
• If auto‑start is ON (Settings → Training), training begins immediately
• Progress popup shows run/percent; “View Logs” focuses Runner
• After training complete, export + re‑eval can run automatically (Models tab handler)
• Per‑chat Tools: ⚙️ → 🔧 lets you override tool set for this chat (diff summary printed in Chat)

FAILURE MODES & FIXES:
• Mount failed: Ensure a model is selected (right panel) and Ollama is reachable; errors show stderr/stdout in Chat.
• No dataset generated: Most recent interaction had no failing/ refusal cases — try a task that exercises tools or enable more tools.
• No re‑eval context: The system applies a strict fallback (suite/prompt/schema) based on variant type.
• Pane resizing: If panes disappear, lock widths (🔒) to persist defaults and disable drag.

DATA PRIVACY:
All data stays local on your machine. Nothing is sent externally."""

        training_mode_label = ttk.Label(
            training_mode_section,
            text=training_mode_text,
            font=("Arial", 9),
            foreground='#aaffaa',
            justify=tk.LEFT,
            wraplength=700
        )
        training_mode_label.pack(padx=10, pady=10, anchor=tk.W)

        # Skill Verification Section
        skills_section = ttk.LabelFrame(content_frame, text="✅ Understanding Skill Verification", style='TLabelframe')
        skills_section.pack(fill=tk.X, padx=10, pady=10)

        skills_text = """DUAL VERIFICATION SYSTEM:
The system shows TWO types of skills to identify false positives.

VERIFIED RUNTIME SKILLS (Green)
• Source: Actual tool usage in Chat Interface
• Criteria: ≥80% success rate with ≥3 attempts
• Meaning: Model REALLY has this skill
• Example: file_read: 15 calls, 93% success → VERIFIED

CLAIMED EVALUATION SKILLS (Yellow)
• Source: Test suite results (Models Tab → Evaluate)
• Warning: May test base model, not your fine-tuned GGUF
• Meaning: Tests say it works, but no runtime proof
• Example: web_search: Passed tests but 0 real usage → CLAIMED

FAILED RUNTIME SKILLS (Red)
• Source: Runtime usage with poor success rate
• Criteria: <80% success rate
• Meaning: Model tried but failed
• Action: Generate corrective training data

WHY DUAL VERIFICATION MATTERS:
The evaluation tests run against the base PyTorch model, but you're
using the fine-tuned GGUF. This can create FALSE POSITIVES where
tests pass but the actual model fails.

Runtime verification proves skills by actual usage, not just tests.

HOW TO INTERPRET:
• Green + Yellow = Truly verified skill
• Yellow only = Possible false positive, needs runtime testing
• Red = Needs training
• No color = Never tested or used"""

        skills_label = ttk.Label(
            skills_section,
            text=skills_text,
            font=("Arial", 9),
            foreground='#ffffaa',
            justify=tk.LEFT,
            wraplength=700
        )
        skills_label.pack(padx=10, pady=10, anchor=tk.W)

        # Training Data Section
        training_data_section = ttk.LabelFrame(content_frame, text="📦 Training Data Generation", style='TLabelframe')
        training_data_section.pack(fill=tk.X, padx=10, pady=10)

        training_data_text = """THREE AUTOMATED SOURCES:

1. RUNTIME LOG CONVERSION
   Location: Chat Interface → "Export Runtime to Training"
   What: Converts tool call logs to training format
   Best for: Models with lots of usage data
   Output: Training_Data-Sets/Training/{model}_runtime_{timestamp}.jsonl

2. CHAT HISTORY EXTRACTION
   Location: Chat Interface → "Extract Chat Training Data"
   What: Extracts successful conversation patterns
   Filters: Min tool calls, successful only
   Best for: High-quality conversational patterns
   Output: Training_Data-Sets/Training/chat_extracted_{model}_{timestamp}.jsonl

3. CORRECTIVE DATA GENERATION
   Location: Evaluation Tab → Auto-triggered on regression
   What: Generates correct examples for failed skills
   Targets: Skills with <60% success rate
   Best for: Fixing specific skill failures
   Output: Training_Data-Sets/Training/{model}_corrective_{timestamp}.jsonl

MANUAL DATA CREATION:
You can also manually create training data in JSONL format:
{"messages": [
  {"role": "user", "content": "Search for Python tutorials"},
  {"role": "assistant", "content": "", "tool_calls": [...]},
  {"role": "tool", "content": "...", "tool_call_id": "..."},
  {"role": "assistant", "content": "I found..."}
]}

COMBINING SOURCES:
For best results, merge multiple sources:
• Runtime logs: Real usage patterns
• Chat extractions: Successful conversations
• Corrective data: Targeted fixes for failures"""

        training_data_label = ttk.Label(
            training_data_section,
            text=training_data_text,
            font=("Arial", 9),
            foreground='#ffaaff',
            justify=tk.LEFT,
            wraplength=700
        )
        training_data_label.pack(padx=10, pady=10, anchor=tk.W)

        # Regression Detection Section
        regression_section = ttk.LabelFrame(content_frame, text="⚠️ Regression Detection & Auto-Correction", style='TLabelframe')
        regression_section.pack(fill=tk.X, padx=10, pady=10)

        regression_text = """WHAT IS REGRESSION?
Regression occurs when a model's skills degrade after training.
Example: file_read was 90% accurate, now it's 75% after fine-tuning.

HOW DETECTION WORKS:
1. First evaluation creates BASELINE
2. Subsequent evaluations compare to baseline
3. Skills that drop >5% accuracy = REGRESSED
4. System identifies specific skills that degraded

AUTO-CORRECTION FLOW:
When regression detected:
1. EvaluationEngine.auto_trigger_corrective_training() runs
2. Identifies regressed skills (e.g., ["file_read", "web_search"])
3. Generates corrective training data from:
   - Runtime failures (shows what went wrong)
   - Chat history successes (shows correct patterns)
4. Saves corrective data files
5. Provides re-training recommendation

MANUAL REGRESSION CHECK:
• Go to Models Tab
• Click "Evaluate Model"
• Review evaluation report for regressions
• If found, check Training_Data-Sets/Training/ for corrective files

RE-TRAINING AFTER REGRESSION:
1. Use generated corrective training data
2. Reduce learning rate (try 1e-4 instead of 2e-4)
3. Fewer epochs (1-2) to avoid over-fitting
4. Re-evaluate to confirm improvement

PREVENTION TIPS:
• Don't over-train (3 epochs is usually enough)
• Use diverse training data
• Keep learning rate moderate (2e-4 default)
• Regular evaluation checks after training"""

        regression_label = ttk.Label(
            regression_section,
            text=regression_text,
            font=("Arial", 9),
            foreground='#ffaa88',
            justify=tk.LEFT,
            wraplength=700
        )
        regression_label.pack(padx=10, pady=10, anchor=tk.W)

        # Troubleshooting Section
        troubleshooting_section = ttk.LabelFrame(content_frame, text="🔧 Troubleshooting Common Issues", style='TLabelframe')
        troubleshooting_section.pack(fill=tk.X, padx=10, pady=10)

        troubleshooting_text = """ISSUE: "Model shows skills but fails in chat"
SOLUTION: False positive from evaluation. The test ran on base model,
          not your GGUF. Enable Training Mode and collect real usage data.

ISSUE: "Training data file is empty"
SOLUTION: No tool calls logged yet. Enable Training Mode and use the
          model with tools before exporting training data.

ISSUE: "Skills not improving after training"
SOLUTION:
  1. Check training data quality (open JSONL file)
  2. Increase epochs (try 5-10)
  3. Increase LoRA rank (try r=32)
  4. Ensure training data matches your use case

ISSUE: "Runtime scores not updating"
SOLUTION: Scores persist to config.py on:
  - Model switch
  - Training mode disable
  - Manual export
  Check Models Tab to verify persistence.

ISSUE: "Can't find generated training data"
SOLUTION: Check Training_Data-Sets/Training/ directory.
          Files named: {model}_runtime_{timestamp}.jsonl

ISSUE: "Regression detected after every training"
SOLUTION: You may be over-training. Reduce:
  - Epochs: 1-2 instead of 3+
  - Learning rate: 1e-4 instead of 2e-4
  - Use more diverse training data

ISSUE: "Models Tab shows no skills"
SOLUTION:
  1. Run evaluation first (Models Tab → Evaluate)
  2. Or use model in chat with Training Mode enabled
  3. Skills appear after either evaluation or runtime usage"""

        troubleshooting_label = ttk.Label(
            troubleshooting_section,
            text=troubleshooting_text,
            font=("Arial", 9),
            foreground='#ff8888',
            justify=tk.LEFT,
            wraplength=700
        )
        troubleshooting_label.pack(padx=10, pady=10, anchor=tk.W)

        # Best Practices Section
        best_practices_section = ttk.LabelFrame(content_frame, text="⭐ Best Practices", style='TLabelframe')
        best_practices_section.pack(fill=tk.X, padx=10, pady=10)

        best_practices_text = """MODEL LIFECYCLE:
1. Download → 2. Evaluate → 3. Runtime Test → 4. Collect Data →
5. Generate Training → 6. Fine-tune → 7. Re-evaluate → 8. Deploy

DATA COLLECTION:
• Collect at least 20-30 tool calls before training
• Use diverse tasks covering all tool types
• Include both successes and failures for balance
• Save conversations with good tool usage patterns

TRAINING:
• Start with defaults: 3 epochs, 2e-4 LR, r=16, alpha=32
• Use batch size 2 for 8GB RAM, 4 for 16GB+
• Combine multiple training data sources for best results
• Always run evaluation after training

SKILL VERIFICATION:
• Trust VERIFIED (green) skills - they're proven
• Test CLAIMED (yellow) skills - they may be false positives
• Re-train FAILED (red) skills with corrective data
• Regularly review Models Tab for skill status

REGRESSION HANDLING:
• Check for regressions after every training run
• Use auto-generated corrective data
• Reduce training intensity if regression persists
• Keep baseline evaluation for comparison

SYSTEM MAINTENANCE:
• Clear old logs periodically (Settings → Clear Cache)
• Archive successful training data for reuse
• Keep lineage.json for model tracking
• Regular evaluations to monitor skill drift"""

        best_practices_label = ttk.Label(
            best_practices_section,
            text=best_practices_text,
            font=("Arial", 9),
            foreground='#88ffff',
            justify=tk.LEFT,
            wraplength=700
        )
        best_practices_label.pack(padx=10, pady=10, anchor=tk.W)

    def _on_tab_visibility_changed(self):
        """Callback when a tab visibility checkbox is toggled."""
        # Immediately save settings to persist the change
        self.save_settings_to_file()
        messagebox.showinfo("Tab Visibility Changed", "Tab visibility settings saved. Please Quick Restart the application to apply changes.")

    def _collect_assignable_agents(self) -> list[dict]:
        """Return the roster of configured agents from any available source."""
        agents: list[dict] = []
        seen: set[str] = set()

        def _extend(entries: Optional[List[dict]], label: str) -> None:
            for entry in self._normalize_agent_roster(entries):
                name = entry.get('name')
                if not name or name in seen:
                    continue
                agents.append(entry)
                seen.add(name)

        app = getattr(self, 'main_gui', None)
        custom_tab = None
        if app and hasattr(app, 'custom_code_tab'):
            custom_tab = getattr(app, 'custom_code_tab', None)
        if not custom_tab:
            custom_tab = getattr(self.root, 'custom_code_tab', None)

        agents_tab = getattr(custom_tab, 'agents_tab', None) if custom_tab else None
        if agents_tab and hasattr(agents_tab, '_current_roster'):
            try:
                _extend(agents_tab._current_roster(), 'configured_roster')
            except Exception as exc:
                log_message(f"SETTINGS: Unable to collect configured agent roster: {exc}")

        if custom_tab and hasattr(custom_tab, '_collect_known_agents'):
            try:
                _extend(custom_tab._collect_known_agents(), 'known_agents')
            except Exception as exc:
                log_message(f"SETTINGS: Unable to collect agent roster from Custom Code tab: {exc}")

        roster_source = None
        if app and hasattr(app, 'get_active_agents') and callable(getattr(app, 'get_active_agents')):
            roster_source = app
        elif hasattr(self.root, 'get_active_agents') and callable(getattr(self.root, 'get_active_agents')):
            roster_source = self.root
        if roster_source:
            try:
                _extend(roster_source.get_active_agents() or [], 'active_roster')
            except Exception as exc:
                log_message(f"SETTINGS: Unable to read active agents roster: {exc}")

        if not agents:
            _extend(self._load_runtime_roster_snapshot(), 'runtime_snapshot')

        return agents

    def _resolve_planner_roster_entry(self) -> Optional[dict]:
        """Return the published planner agent entry (requires Agents tab → ✓ Set Agent)."""
        try:
            for entry in self._collect_assignable_agents():
                role = (entry.get('role') or '').strip().lower()
                name = (entry.get('name') or '').strip()
                if role == 'planner' and name:
                    return entry
        except Exception as exc:
            log_message(f"SETTINGS: Unable to resolve planner roster entry: {exc}")
            if _settings_debug_logger:
                _settings_debug_logger.error("Failed to resolve planner roster entry", exc_info=exc)
        return None

    def _normalize_agent_roster(self, entries: Optional[List[dict]]) -> list[dict]:
        normalized: list[dict] = []
        for entry in entries or []:
            normalized_entry = self._normalize_agent_entry(entry)
            if normalized_entry:
                normalized.append(normalized_entry)
        return normalized

    @staticmethod
    def _normalize_agent_entry(entry: dict | None) -> dict | None:
        if not isinstance(entry, dict):
            return None
        name = entry.get('name') or entry.get('display_name') or entry.get('agent_id')
        if not name:
            return None
        role = entry.get('role') or entry.get('assigned_type') or entry.get('agent_type') or entry.get('type')
        if not role and isinstance(name, str):
            lower = name.lower()
            if lower.endswith('_agent'):
                role = lower[:-7]
            elif '_' in lower:
                role = lower.split('_', 1)[0]
        role = (role or 'general').strip().lower()
        return {'name': name, 'role': role}

    def _load_runtime_roster_snapshot(self) -> list[dict]:
        path = Path('Data') / 'user_prefs' / 'agents_roster.runtime.json'
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(data, list):
                return data
        except Exception as exc:
            log_message(f"SETTINGS: Unable to read runtime agent roster: {exc}")
        return []

    def _build_assignment_record(self, category: str, filename: str, project_name: str | None = None) -> dict | None:
        """Create a task record compatible with the Agents dock dispatcher."""
        try:
            if project_name:
                todo_dir = get_project_todos_dir(project_name) / category
            else:
                todo_dir = TODOS_DIR / category
            filepath = todo_dir / filename
            todo_data = read_todo_file(filepath)
        except Exception as exc:
            log_message(f"SETTINGS: Unable to load todo for assignment ({category}/{filename}): {exc}")
            return None

        roles = [str(r).strip().lower() for r in (todo_data.get('agent_roles') or []) if str(r).strip()]
        assigned_agent = (todo_data.get('assigned_agent') or '').strip()
        assigned_role = (todo_data.get('assigned_agent_role') or '').strip().lower()
        record = {
            'title': todo_data.get('title', filepath.stem),
            'priority': (todo_data.get('priority') or 'low').lower(),
            'category': category,
            'details': todo_data.get('details', ''),
            'plan_keys': self._extract_linked_plan_keys(todo_data),
            'filepath': str(filepath),
            'project_label': project_name or 'System',
            'project_name': project_name,
            'linked_plan': todo_data.get('linked_plan'),
            'agent_roles': roles,
            'living_project_name': todo_data.get('living_project_name') or todo_data.get('project'),
            'living_project_id': todo_data.get('living_project_id'),
            'missing_roles': [],
            'working_dir_hint': todo_data.get('working_dir_hint'),
            'assigned_agent': assigned_agent or None,
            'assigned_agent_role': assigned_role or None,
            'assigned_at': todo_data.get('assigned_at'),
        }
        return record

    def _assign_todo_via_agents_dock(self, record: dict, agent_name: str) -> bool:
        """Delegate assignment to the Agents dock implementation."""
        custom_tab = getattr(self.root, 'custom_code_tab', None)
        if not custom_tab or not hasattr(custom_tab, '_assign_task_to_agent'):
            messagebox.showerror(
                "Agents Dock Unavailable",
                "Unable to locate the Agents dock. Please open the Custom Code tab and try again.",
                parent=self.root
            )
            return False
        try:
            role_availability = custom_tab._get_agent_role_availability()
        except Exception:
            role_availability = None
        try:
            return bool(custom_tab._assign_task_to_agent(agent_name, record, role_availability))
        except Exception as exc:
            log_message(f"SETTINGS: Dock assignment failed: {exc}")
            messagebox.showerror(
                "Assignment Failed",
                "Unable to dispatch this todo to the selected agent. See logs for details.",
                parent=self.root
            )
            return False

    def _get_agent_role_assignment_summary(self, role_key: str) -> tuple[str, str]:
        """
        Return (status, style) describing whether any agent is configured for the role.
        style can be 'info' or 'warning' (used for optional color coding outside).
        """
        normalized = (role_key or '').strip().lower()
        if not normalized or normalized == 'general':
            return ("General tasks can be handled by any agent or unassigned work.", 'info')
        try:
            custom_tab = getattr(self.root, 'custom_code_tab', None)
            matching = []
            if custom_tab and hasattr(custom_tab, '_collect_known_agents'):
                for entry in custom_tab._collect_known_agents():
                    if entry.get('role') == normalized:
                        matching.append(entry.get('name', 'agent'))
            else:
                agents_tab = getattr(custom_tab, 'agents_tab', None) if custom_tab else None
                configs = getattr(agents_tab, 'agent_configs', None) if agents_tab else None
                if isinstance(configs, dict):
                    for agent_id, cfg in configs.items():
                        assigned_type = cfg.get('assigned_type') or cfg.get('agent_type') or cfg.get('type')
                        if isinstance(assigned_type, (list, tuple, set)):
                            values = assigned_type
                        else:
                            values = [assigned_type]
                        for value in values:
                            if str(value).strip().lower() == normalized:
                                matching.append(cfg.get('display_name') or agent_id)
                                break
            if matching:
                return (f"Configured agents: {', '.join(matching)}", 'info')
        except Exception:
            pass
        return ("No agents configured for this role yet. Tasks will remain queued in the Agents Dock until you assign one.", 'warning')
